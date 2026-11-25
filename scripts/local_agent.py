r"""Local LLM agent client against the BIST MCP server.

Replaces the Codex CLI subprocess in `run_agent_demo.py` with an Ollama-hosted model
(OpenAI-compatible endpoint at http://localhost:11434/v1). Supports tool-calling.

Usage (PowerShell):
    ollama serve   # in another terminal, if not already a service
    .\.venv\Scripts\python.exe scripts/local_agent.py --smoke
    .\.venv\Scripts\python.exe scripts/local_agent.py --ticker THYAO.IS --as-of 2025-12-31

The script bridges the model to our stdio MCP server by launching the server as a child
process and shuttling JSON-RPC messages. All inference is local; no cloud calls.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OLLAMA_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
DEFAULT_MODEL = os.environ.get("BIST_LOCAL_MODEL", "qwen2.5:7b-instruct")
SYSTEM_PROMPT = (
    "You are an academic BIST financial-analysis agent. For every claim, call a tool first: "
    "you must never invent numbers. Allowed labels are the 8 educational labels "
    "(HOLD, WATCH, INVESTIGATE, POTENTIAL_CATCH_UP_CANDIDATE, TECHNICAL_REVERSAL_CANDIDATE, "
    "FUNDAMENTAL_IMPROVEMENT_CANDIDATE, REJECT_SIGNAL, ANALYSIS_UNSAFE). When evidence is "
    "insufficient, choose INVESTIGATE or ANALYSIS_UNSAFE. Cite tool names in your reasoning. "
    "Do not give investment advice. Numeric values must come from committed_evidence entries."
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


def _truncate_tool_result(payload: str) -> str:
    if len(payload) <= _TOOL_RESULT_CHAR_CAP:
        return payload
    keep = _TOOL_RESULT_CHAR_CAP - 200
    return payload[:keep] + f"\n...[truncated {len(payload) - keep} chars for context budget]"


def _chat(messages: list[dict], tools: list[dict], model: str,
          temperature: float = 0.0, allow_tools: bool = True) -> dict:
    body: dict = {"model": model, "messages": messages, "temperature": temperature, "stream": False}
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


def run_agent(prompt: str, *, model: str = DEFAULT_MODEL, max_turns: int = 10,
              trace_path: Path | None = None, allow_tools: bool = True,
              force_answer_after: int = 10) -> dict:
    """Run a tool-calling loop against a local Ollama model and the BIST MCP server.

    If ``allow_tools`` is False the MCP server is still launched for schema listing but
    the model is called with an empty tools array and ``tool_choice="none"``, used for
    the stage-A raw-LLM baseline in the harness.

    ``force_answer_after`` — if the model is still making tool calls after this many turns,
    inject a "write your final answer now" nudge and disable further tool calls.  Dedup
    guard: if the model calls the same tool with the identical arguments a second time,
    we return an error immediately (without hitting the MCP server) and ask it to finalise.
    Both guards target the tool-loop pathology documented in MODEL_CARD.md.
    """
    mcp = MCPStdioClient([sys.executable, "-m", "bist_analytics.mcp.server"])
    trace: list[dict] = []
    seen_calls: set[str] = set()  # dedup key: "tool_name:json(args,sorted)"
    tools_active = allow_tools
    try:
        mcp_tools = mcp.list_tools() if allow_tools else []
        openai_tools = [_mcp_tool_to_openai_schema(t) for t in mcp_tools] if allow_tools else []
        messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT},
                                 {"role": "user", "content": prompt}]
        for turn in range(max_turns):
            # Safety net: after force_answer_after tool turns, nudge the model to finalise.
            if tools_active and turn >= force_answer_after and any(e.get("tool") for e in trace):
                messages.append({"role": "user", "content":
                    "You have gathered sufficient evidence. Write your final answer now "
                    "without calling any more tools."})
                tools_active = False
            response = _chat(messages, openai_tools if tools_active else [], model=model,
                             allow_tools=tools_active)
            choice = response["choices"][0]
            message = choice["message"]
            trace.append({"turn": turn, "role": "assistant", "content": message.get("content"),
                           "tool_calls": message.get("tool_calls", [])})
            tool_calls = message.get("tool_calls") or []
            if not tool_calls or not tools_active:
                return {"final_answer": message.get("content", ""), "trace": trace,
                         "turns_used": turn + 1, "model": model}
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
                messages.append({"role": "tool", "tool_call_id": call.get("id", str(time.time())),
                                 "name": call["function"]["name"],
                                 "content": _truncate_tool_result(
                                     json.dumps(tool_result, default=str))})
            # On first dedup hit, disable tools so next turn forces a text answer.
            if dedup_fired and tools_active:
                messages.append({"role": "user", "content":
                    "You already have all the evidence you need. Write your final answer now."})
                tools_active = False
        return {"final_answer": "MAX_TURNS_EXCEEDED", "trace": trace,
                 "turns_used": max_turns, "model": model}
    finally:
        mcp.close()
        if trace_path is not None:
            trace_path.parent.mkdir(parents=True, exist_ok=True)
            # Harness scripts consume the trace as JSONL; also writeable as plain JSON.
            if trace_path.suffix == ".jsonl":
                with trace_path.open("w", encoding="utf-8") as fh:
                    for entry in trace:
                        fh.write(json.dumps(entry, default=str) + "\n")
            else:
                trace_path.write_text(json.dumps({"trace": trace}, indent=2, default=str),
                                       encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Local Ollama-driven BIST MCP agent.")
    parser.add_argument("--smoke", action="store_true", help="Run a one-tool smoke test.")
    parser.add_argument("--ticker", default="THYAO.IS")
    parser.add_argument("--as-of", default="2025-12-31")
    parser.add_argument("--model", default=DEFAULT_MODEL)
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
    result = run_agent(prompt, model=args.model, trace_path=trace_path)
    out = ROOT / "outputs/agent/local_agent.result.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"final_answer_head": result["final_answer"][:400],
                      "turns_used": result["turns_used"],
                      "trace": str(trace_path),
                      "result": str(out)}, indent=2))


if __name__ == "__main__":
    main()
