r"""Local LLM agent client against the BIST MCP server.

Replaces the Codex CLI subprocess in `run_agent_demo.py` with an Ollama-hosted model
(OpenAI-compatible endpoint at http://localhost:11434/v1). Supports tool-calling.

Usage (PowerShell):
    ollama serve   # in another terminal, if not already a service
    .\.venv\Scripts\python.exe scripts/local_agent.py --smoke --model bist-qwen
    .\.venv\Scripts\python.exe scripts/local_agent.py --ticker THYAO.IS --as-of 2025-12-31 --model bist-qwen
    (without --model or BIST_LOCAL_MODEL the default is qwen2.5:7b-instruct)

The script bridges the model to our stdio MCP server by launching the server as a child
process and shuttling JSON-RPC messages. All inference is local; no cloud calls.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
OLLAMA_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
DEFAULT_MODEL = os.environ.get("BIST_LOCAL_MODEL", "qwen2.5:7b-instruct")
# The agent's MCP server must see the multi-ticker universe; without BIST_CONFIG the
# server falls back to config/project.yaml (THYAO only, no sector map) and sector tools
# fail with UNIVERSE_UNCONFIGURED.
DEFAULT_CONFIG = os.environ.get("BIST_AGENT_CONFIG", "config/universe_live.yaml")
DEFAULT_SEED = 17
DEFAULT_TEMPERATURE = 0.0
TRACE_SCHEMA = "bist-execution-trace/1"
SYSTEM_PROMPT = (
    "You are an academic BIST financial-analysis agent. For every claim, call a tool first: "
    "you must never invent numbers. Allowed labels are the 8 educational labels "
    "(HOLD, WATCH, INVESTIGATE, POTENTIAL_CATCH_UP_CANDIDATE, TECHNICAL_REVERSAL_CANDIDATE, "
    "FUNDAMENTAL_IMPROVEMENT_CANDIDATE, REJECT_SIGNAL, ANALYSIS_UNSAFE). When evidence is "
    "insufficient, choose INVESTIGATE or ANALYSIS_UNSAFE. Cite tool names in your reasoning. "
    "Do not give investment advice. Numeric values must come from committed_evidence entries."
)
# Used by the presentation runner and the live-question CLI. It starts with the training-time
# SYSTEM_PROMPT verbatim and adds a generic tool-routing guide: which tool family answers
# which *kind* of question. It holds no answers, tickers or numbers for any specific question.
PRESENTATION_SYSTEM_PROMPT = SYSTEM_PROMPT + (
    "\n\nTool guide (pick what the question needs; pass the question's ticker and dates):\n"
    "- sector leaders/laggards, catch-up: rank_sector_relative_strength (as_of, lookback)\n"
    "- day-of-week effects: test_weekday_pattern (ticker, start, end)\n"
    "- reversal / turning-point events: detect_reversal_events (ticker, as_of, lookback<=252)\n"
    "- fundamentals and their change: get_fundamental_metrics, calculate_fundamental_change; "
    "price reaction: get_stock_history, get_news_events\n"
    "- technical state and scores: calculate_indicators, calculate_scores, generate_signal\n"
    "- dates beyond the data, unknown tickers, missing data: check_data_quality (ticker, as_of); "
    "gate_status HARD_BLOCK means the label must be ANALYSIS_UNSAFE\n"
    "- methodology, definitions, disclosures: search_knowledge_base\n"
    "Apply the label_rule returned by the tool. If a tool returns an error or available=false, "
    "say the data is unavailable; never estimate it. Copy numbers exactly as the tools return "
    "them (you may round, or convert fractions to percentages)."
)


# ---------- MCP stdio client (minimal; one connection per run) --------------------------

class MCPStdioClient:
    def __init__(self, command: list[str], env: dict[str, str] | None = None) -> None:
        child_env = os.environ.copy()
        if env:
            child_env.update(env)
        # Redirect stderr to DEVNULL so the child never blocks on a full stderr pipe
        # (we don't read it). Chatty warnings from pandas/yfinance can fill the default
        # 64 KB OS buffer after a few hundred tool calls and deadlock the server.
        self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.DEVNULL, cwd=str(ROOT), bufsize=0,
                                        env=child_env)
        self.counter = 0
        self._initialize()

    def _rpc(self, method: str, params: dict | None = None) -> Any:
        self.counter += 1
        request = {"jsonrpc": "2.0", "id": self.counter, "method": method, "params": params or {}}
        payload = (json.dumps(request) + "\n").encode("utf-8")
        assert self.process.stdin is not None and self.process.stdout is not None
        self.process.stdin.write(payload)
        self.process.stdin.flush()
        while True:
            line = self.process.stdout.readline()
            if not line:
                raise RuntimeError(f"MCP server closed before responding to {method}")
            try:
                message = json.loads(line.decode("utf-8"))
            except json.JSONDecodeError:
                continue
            if message.get("id") == self.counter:
                if "error" in message:
                    raise RuntimeError(f"MCP {method} error: {message['error']}")
                return message.get("result")

    def _initialize(self) -> None:
        self._rpc("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                                  "clientInfo": {"name": "bist-local-agent", "version": "0.1.0"}})
        # per MCP spec, no response required for notifications/initialized
        assert self.process.stdin is not None
        self.process.stdin.write((json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"})
                                  + "\n").encode("utf-8"))
        self.process.stdin.flush()

    def list_tools(self) -> list[dict]:
        result = self._rpc("tools/list")
        return result.get("tools", [])

    def call_tool(self, name: str, arguments: dict) -> dict:
        return self._rpc("tools/call", {"name": name, "arguments": arguments})

    def close(self) -> None:
        try:
            self.process.terminate()
            self.process.wait(timeout=5)
        except Exception:
            self.process.kill()


# ---------- Ollama OpenAI-compatible client ---------------------------------------------

def _mcp_tool_to_openai_schema(tool: dict) -> dict:
    """Translate an MCP tool descriptor into OpenAI-tool-calling format."""
    return {"type": "function", "function": {
        "name": tool["name"],
        "description": (tool.get("description") or "").strip(),
        "parameters": tool.get("inputSchema", {"type": "object", "properties": {}})}}


# Qwen 2.5's advertised context is 32k and Ollama refuses to go higher regardless of
# the Modelfile num_ctx. detect_reversal_events and run_backtest alone can emit ~20k
# tokens of JSON; after 3-4 tool rounds the request overflows. Cap each tool-result
# payload so model + system + user + N tool outputs still fit. 12 KB ≈ 3 K tokens,
# which leaves headroom for 6-7 rounds under 32k. Both baseline and fine-tuned models
# see the same cap, so comparisons stay apples-to-apples.
_TOOL_RESULT_CHAR_CAP = 12_000


def _truncate_tool_result(payload: str, cap: int = _TOOL_RESULT_CHAR_CAP) -> str:
    if len(payload) <= cap:
        return payload
    keep = cap - 200
    return payload[:keep] + f"\n...[truncated {len(payload) - keep} chars for context budget]"


def model_view(tool_result: Any) -> str:
    """The exact text the model sees for a tool result (before the size cap).

    MCP results carry the payload twice (pretty-printed text content + structuredContent);
    the model gets one compact JSON copy of the structured payload. Errors keep their text.
    The execution trace always stores the full, untouched MCP result.
    """
    if isinstance(tool_result, dict):
        structured = tool_result.get("structuredContent")
        if structured is not None and not tool_result.get("isError"):
            return json.dumps(structured, default=str, ensure_ascii=False, separators=(",", ":"))
        content = tool_result.get("content")
        if isinstance(content, list) and content and isinstance(content[0], dict):
            text = "\n".join(str(c.get("text", "")) for c in content)
            return json.dumps({"isError": bool(tool_result.get("isError")), "text": text},
                              ensure_ascii=False)
    return json.dumps(tool_result, default=str, ensure_ascii=False, separators=(",", ":"))


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def _sha256(obj: Any) -> str:
    data = obj if isinstance(obj, str) else json.dumps(obj, sort_keys=True, default=str)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _ollama_native(path: str, body: dict | None = None) -> dict | None:
    """Call Ollama's native /api/* endpoints (model metadata). Returns None if unavailable."""
    base = OLLAMA_URL.rstrip("/").removesuffix("/v1")
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(f"{base}{path}", data=data,
                                     headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read())
    except (urllib.error.URLError, OSError, ValueError):
        return None


def model_provenance(model: str) -> dict:
    """Name, digest, family, size, quantization and Modelfile parameters of the served model."""
    info: dict[str, Any] = {"name": model, "endpoint": OLLAMA_URL}
    version = _ollama_native("/api/version")
    info["ollama_version"] = (version or {}).get("version")
    tags = _ollama_native("/api/tags") or {}
    for entry in tags.get("models", []):
        if entry.get("name") in (model, f"{model}:latest") or entry.get("model") in (model, f"{model}:latest"):
            info["digest"] = entry.get("digest")
            info["size_bytes"] = entry.get("size")
            info["modified_at"] = entry.get("modified_at")
            break
    show = _ollama_native("/api/show", {"model": model}) or {}
    details = show.get("details") or {}
    info.update({"family": details.get("family"), "parameter_size": details.get("parameter_size"),
                 "quantization_level": details.get("quantization_level"),
                 "format": details.get("format"),
                 "modelfile_parameters": show.get("parameters"),
                 "modelfile_sha256": _sha256(show["modelfile"]) if show.get("modelfile") else None})
    manifest = ROOT / "submission.json"
    if manifest.exists():
        try:
            sub = json.loads(manifest.read_text(encoding="utf-8"))
            info["base_model"] = sub.get("base_model")
            info["adapter_sha256"] = (sub.get("adapter") or {}).get("sha256")
        except ValueError:
            pass
    return info


def _modelfile_param(provenance: dict, key: str) -> str | None:
    for line in (provenance.get("modelfile_parameters") or "").splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] == key:
            return parts[1]
    return None


def _git_state() -> dict:
    def git(*args: str) -> str:
        try:
            return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                                  check=True).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            return ""
    return {"commit": git("rev-parse", "HEAD") or None,
            "dirty": bool(git("status", "--porcelain", "--untracked-files=no"))}


_ISO_DATE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
_TICKER = re.compile(r"\b([A-Z][A-Z0-9]{2,5}\.IS)\b")
_DATE_KEYS = ("as_of", "start", "end", "lookback", "sessions", "window")


def _date_range(args: dict) -> dict | None:
    picked = {k: args[k] for k in _DATE_KEYS if k in args}
    return picked or None


def _chat(messages: list[dict], tools: list[dict], model: str,
          temperature: float = DEFAULT_TEMPERATURE, allow_tools: bool = True,
          seed: int | None = DEFAULT_SEED) -> dict:
    body: dict = {"model": model, "messages": messages, "temperature": temperature, "stream": False}
    if seed is not None:
        body["seed"] = seed  # Ollama's OpenAI-compatible endpoint forwards this to the sampler
    if allow_tools and tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"
    data = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(f"{OLLAMA_URL}/chat/completions", data=data,
                                      headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=600) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:2000]
        raise RuntimeError(f"Ollama HTTP {exc.code} at {OLLAMA_URL}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Ollama endpoint unreachable at {OLLAMA_URL}: {exc}") from exc


_RAG_SNIPPET_CHARS = 300


def _retrieval_args(prompt: str, top_k: int) -> dict:
    """Generic (question-agnostic) extraction of the KB filter from the user's question."""
    args: dict[str, Any] = {"query": prompt[:500], "top_k": top_k}
    dates = sorted(_ISO_DATE.findall(prompt))
    if dates:
        args["as_of"] = dates[-1]  # latest date mentioned = the information horizon
    tickers = _TICKER.findall(prompt)
    if len(set(tickers)) == 1:
        args["ticker"] = tickers[0]
    return args


def _format_reference_context(result: dict) -> str | None:
    hits = (((result or {}).get("structuredContent") or {}).get("data") or {}).get("hits")
    if hits is None:
        # MCP SDKs may only return the JSON as text content.
        for block in (result or {}).get("content") or []:
            try:
                hits = json.loads(block.get("text", "")).get("data", {}).get("hits")
                break
            except (ValueError, AttributeError):
                continue
    if not hits:
        return None
    lines = ["Reference context retrieved by search_knowledge_base (cite doc_id when you use "
             "it; numbers must still come from tool results):"]
    for h in hits:
        text = h.get("text", "")
        lines.append(f"- [{h['doc_id']}] {h.get('title', '')} ({h.get('published_at') or 'undated'}): "
                     f"{text[:_RAG_SNIPPET_CHARS]}{'...' if len(text) > _RAG_SNIPPET_CHARS else ''}")
    return "\n".join(lines)


def run_agent(prompt: str, *, model: str = DEFAULT_MODEL, max_turns: int = 10,
              trace_path: Path | None = None, allow_tools: bool = True,
              force_answer_after: int = 10, temperature: float = DEFAULT_TEMPERATURE,
              seed: int | None = DEFAULT_SEED, config: str | None = DEFAULT_CONFIG,
              retrieval_top_k: int = 3, system_prompt: str = SYSTEM_PROMPT,
              scenario_id: str | None = None, on_event: Any = None) -> dict:
    """Run a tool-calling loop against a local Ollama model and the BIST MCP server.

    If ``allow_tools`` is False the MCP server is still launched for schema listing but
    the model is called with an empty tools array and ``tool_choice="none"``, used for
    the stage-A raw-LLM baseline in the harness.

    ``force_answer_after`` — if the model is still making tool calls after this many turns,
    inject a "write your final answer now" nudge and disable further tool calls.  Dedup
    guard: if the model calls the same tool with the identical arguments a second time,
    we return an error immediately (without hitting the MCP server) and ask it to finalise.
    Both guards target the tool-loop pathology documented in MODEL_CARD.md.

    ``retrieval_top_k`` > 0 makes the harness call ``search_knowledge_base`` once before
    the first model turn and append the hits to the user message (RAG). The call is a real
    MCP tool call and is recorded as a step with ``actor: "harness"``.

    The returned dict keeps the legacy keys (``final_answer``, ``trace``, ``turns_used``,
    ``model``) and adds ``execution_trace``: the full provenance record written to
    ``trace_path`` (``.json``). A ``.jsonl`` trace_path keeps the legacy step-list format.
    """
    from bist_analytics.harness.grounding import audit_answer

    emit = on_event or (lambda *_: None)
    started = _now()
    t0 = time.perf_counter()
    env = {"BIST_CONFIG": str(ROOT / config)} if config else None
    mcp = MCPStdioClient([sys.executable, "-m", "bist_analytics.mcp.server"], env=env)
    trace: list[dict] = []          # legacy step list (consumed by harness/evaluation code)
    steps: list[dict] = []          # full provenance steps
    seen_calls: set[str] = set()    # dedup key: "tool_name:json(args,sorted)"
    tools_active = allow_tools
    text_retry_used = False
    provenance = model_provenance(model)
    sampling = {"temperature": temperature, "seed": seed,
                "top_p": _modelfile_param(provenance, "top_p"),
                "num_ctx": _modelfile_param(provenance, "num_ctx"),
                "endpoint": f"{OLLAMA_URL}/chat/completions"}
    retrieval: dict[str, Any] | None = None
    user_message = prompt
    final_answer = "MAX_TURNS_EXCEEDED"
    turns_used = max_turns
    error: str | None = None
    openai_tools: list[dict] = []

    def tool_step(turn: int, actor: str, name: str, args: dict, result: Any, started_at: str,
                  seconds: float, sent: str | None) -> None:
        steps.append({"index": len(steps), "turn": turn, "type": "tool_call", "actor": actor,
                      "tool": name, "arguments": args, "date_range": _date_range(args),
                      "started_at": started_at, "finished_at": _now(),
                      "duration_s": round(seconds, 3), "result": result,
                      "result_sha256": _sha256(result),
                      "truncated_for_model": sent is not None and len(sent) > _TOOL_RESULT_CHAR_CAP})
        emit("tool", name, args)

    try:
        mcp_tools = mcp.list_tools() if allow_tools else []
        openai_tools = [_mcp_tool_to_openai_schema(t) for t in mcp_tools] if allow_tools else []
        if allow_tools and retrieval_top_k > 0 and any(t["name"] == "search_knowledge_base"
                                                       for t in mcp_tools):
            r_args = _retrieval_args(prompt, retrieval_top_k)
            r_start, r_t = _now(), time.perf_counter()
            try:
                r_result = mcp.call_tool("search_knowledge_base", r_args)
            except Exception as exc:  # noqa: BLE001 - retrieval failure must not kill the run
                r_result = {"error": str(exc)}
            tool_step(-1, "harness", "search_knowledge_base", r_args, r_result, r_start,
                      time.perf_counter() - r_t, None)
            context = _format_reference_context(r_result)
            retrieval = {"tool": "search_knowledge_base", "arguments": r_args,
                         "step_index": len(steps) - 1, "injected": context is not None,
                         "injected_text": context}
            if context:
                user_message = f"{prompt}\n\n{context}"
        messages: list[dict] = [{"role": "system", "content": system_prompt},
                                {"role": "user", "content": user_message}]
        for turn in range(max_turns):
            # Safety net: after force_answer_after tool turns, nudge the model to finalise.
            if tools_active and turn >= force_answer_after and any(e.get("tool") for e in trace):
                nudge = ("You have gathered sufficient evidence. Write your final answer now "
                         "without calling any more tools.")
                messages.append({"role": "user", "content": nudge})
                steps.append({"index": len(steps), "turn": turn, "type": "harness_message",
                              "reason": "force_answer_after", "content": nudge, "ts": _now()})
                tools_active = False
            call_start, ct = _now(), time.perf_counter()
            emit("thinking", turn, None)
            response = _chat(messages, openai_tools if tools_active else [], model=model,
                             allow_tools=tools_active, temperature=temperature, seed=seed)
            choice = response["choices"][0]
            message = choice["message"]
            tool_calls = message.get("tool_calls") or []
            trace.append({"turn": turn, "role": "assistant", "content": message.get("content"),
                          "tool_calls": message.get("tool_calls", [])})
            steps.append({"index": len(steps), "turn": turn, "type": "assistant",
                          "started_at": call_start, "finished_at": _now(),
                          "duration_s": round(time.perf_counter() - ct, 3),
                          "content": message.get("content"),
                          "tool_calls": [{"name": c["function"]["name"],
                                          "arguments": c["function"].get("arguments")}
                                         for c in tool_calls],
                          "finish_reason": choice.get("finish_reason"),
                          "usage": response.get("usage"),
                          "system_fingerprint": response.get("system_fingerprint")})
            if not tool_calls or not tools_active:
                content = message.get("content", "") or ""
                if "<tool_call>" in content and not text_retry_used and turn + 1 < max_turns:
                    # The model wrote a tool call as plain text after tools were disabled.
                    # Ask once for a prose answer; the original reply stays in the trace.
                    text_retry_used = True
                    nudge = ("Tools are no longer available. Write your final answer in plain "
                             "text, using only the tool results above.")
                    messages.extend([{"role": "assistant", "content": content},
                                     {"role": "user", "content": nudge}])
                    steps.append({"index": len(steps), "turn": turn, "type": "harness_message",
                                  "reason": "tool_call_as_text", "content": nudge, "ts": _now()})
                    tools_active = False
                    continue
                final_answer, turns_used = content, turn + 1
                break
            messages.append(message)
            dedup_fired = False
            for call in tool_calls:
                try:
                    args = json.loads(call["function"].get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}
                # Dedup guard: on the first repeat call, disable tools immediately so the next
                # turn forces a text answer. Use "dedup_note" (not "error") so the evaluator
                # does not count this as an invalid tool call — it is not an MCP failure.
                call_key = f"{call['function']['name']}:{json.dumps(args, sort_keys=True)}"
                tc_start, tct = _now(), time.perf_counter()
                if call_key in seen_calls:
                    tool_result = {"dedup_note": (f"Already called {call['function']['name']} "
                                                  "with these exact arguments. Use the previous "
                                                  "result and write your final answer now.")}
                    dedup_fired = True
                else:
                    seen_calls.add(call_key)
                    try:
                        tool_result = mcp.call_tool(call["function"]["name"], args)
                    except Exception as exc:  # noqa: BLE001 - surface tool errors to the model
                        tool_result = {"error": str(exc)}
                trace.append({"turn": turn, "tool": call["function"]["name"],
                              "arguments": args, "result": tool_result})
                sent = model_view(tool_result)
                tool_step(turn, "model", call["function"]["name"], args, tool_result, tc_start,
                          time.perf_counter() - tct, sent)
                messages.append({"role": "tool", "tool_call_id": call.get("id", str(time.time())),
                                 "name": call["function"]["name"],
                                 "content": _truncate_tool_result(sent)})
            # On first dedup hit, disable tools so next turn forces a text answer.
            if dedup_fired and tools_active:
                nudge = "You already have all the evidence you need. Write your final answer now."
                messages.append({"role": "user", "content": nudge})
                steps.append({"index": len(steps), "turn": turn, "type": "harness_message",
                              "reason": "dedup_guard", "content": nudge, "ts": _now()})
                tools_active = False
    except Exception as exc:  # noqa: BLE001 - record the failure in the trace, then re-raise
        error = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        mcp.close()
        evidence = [s["result"] for s in steps if s["type"] == "tool_call"]
        grounding = audit_answer(final_answer if error is None else "", evidence,
                                 prompt_texts=[prompt, system_prompt])
        execution_trace = {
            "schema_version": TRACE_SCHEMA,
            "run_id": str(uuid.uuid4()),
            "scenario_id": scenario_id,
            "started_at": started,
            "finished_at": _now(),
            "wall_time_s": round(time.perf_counter() - t0, 3),
            "model": provenance,
            "sampling": sampling,
            "harness": {"script": "scripts/local_agent.py", "config_file": config,
                        "max_turns": max_turns, "force_answer_after": force_answer_after,
                        "tool_result_char_cap": _TOOL_RESULT_CHAR_CAP,
                        "tools_offered": [t["function"]["name"] for t in openai_tools],
                        "git": _git_state(), "python": sys.version.split()[0]},
            "system_prompt": system_prompt,
            "user_prompt": prompt,
            "user_message_sent": user_message,
            "retrieval": retrieval,
            "steps": steps,
            "tools_called": [s["tool"] for s in steps
                             if s["type"] == "tool_call" and s["actor"] == "model"],
            "final_answer": final_answer,
            "turns_used": turns_used,
            "grounding_audit": grounding,
            "error": error,
        }
        if trace_path is not None:
            trace_path.parent.mkdir(parents=True, exist_ok=True)
            # Harness scripts consume the legacy step list as JSONL; .json gets the full record.
            if trace_path.suffix == ".jsonl":
                with trace_path.open("w", encoding="utf-8") as fh:
                    for entry in trace:
                        fh.write(json.dumps(entry, default=str) + "\n")
            else:
                trace_path.write_text(json.dumps(execution_trace, indent=2, default=str,
                                                 ensure_ascii=False), encoding="utf-8")
    return {"final_answer": final_answer, "trace": trace, "turns_used": turns_used,
            "model": model, "execution_trace": execution_trace}


def main() -> None:
    parser = argparse.ArgumentParser(description="Local Ollama-driven BIST MCP agent.")
    parser.add_argument("--smoke", action="store_true", help="Run a one-tool smoke test.")
    parser.add_argument("--ticker", default="THYAO.IS")
    parser.add_argument("--as-of", default="2025-12-31")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--config", default=DEFAULT_CONFIG,
                        help="Config the MCP server loads (BIST_CONFIG).")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--temperature", type=float, default=DEFAULT_TEMPERATURE)
    parser.add_argument("--rag-top-k", type=int, default=3,
                        help="Knowledge-base hits injected before the first turn (0 disables RAG).")
    parser.add_argument("--max-turns", type=int, default=10)
    parser.add_argument("--output", default=None, help="Optional path to dump the full trace JSON.")
    parser.add_argument("--prompt", default=None,
                        help="Free-form user question. Overrides --smoke and the default analysis prompt.")
    args = parser.parse_args()

    if args.prompt:
        prompt = args.prompt
    elif args.smoke:
        prompt = ("Call project_status exactly once. Report its ticker and fundamental source. "
                  "Then stop and summarize in two sentences.")
    else:
        prompt = (f"Analyze {args.ticker} as of {args.as_of}. Call calculate_indicators, "
                  "calculate_scores, generate_signal and check_data_quality. Commit evidence_ids "
                  "and choose one of the 8 educational labels. If data is missing choose "
                  "INVESTIGATE or ANALYSIS_UNSAFE. Keep the explanation under 200 words.")

    trace_path = Path(args.output) if args.output else ROOT / "outputs/agent/local_agent.trace.json"
    result = run_agent(prompt, model=args.model, trace_path=trace_path, config=args.config,
                       seed=args.seed, temperature=args.temperature,
                       retrieval_top_k=0 if args.smoke else args.rag_top_k,
                       max_turns=args.max_turns)
    out = ROOT / "outputs/agent/local_agent.result.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    audit = result["execution_trace"]["grounding_audit"]
    print(json.dumps({"final_answer_head": result["final_answer"][:400],
                      "turns_used": result["turns_used"],
                      "grounding": {"all_grounded": audit["all_grounded"],
                                    "ungrounded": [f["text"] for f in audit["ungrounded"]]},
                      "trace": str(trace_path),
                      "result": str(out)}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
