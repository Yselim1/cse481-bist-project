r"""Run the five presentation scenarios through the local model and save full execution traces.

    .\.venv\Scripts\python.exe scripts/run_presentation_scenarios.py               # all five
    .\.venv\Scripts\python.exe scripts/run_presentation_scenarios.py --only S1 S5
    .\.venv\Scripts\python.exe scripts/run_presentation_scenarios.py --render-only  # rebuild HTML

Each scenario goes through ``scripts/local_agent.run_agent``, the same code path as the
live-question CLI (``scripts/ask.py``). The answer is written exactly as the model produced
it. Nothing in this script edits, filters or substitutes model output.

Outputs (``outputs/presentation/``):
  traces/S1.trace.json ... S5.trace.json   full provenance record per question
  index.json                               summary + SHA-256 of every trace
  traces.html                              human-readable view for the classroom
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.local_agent import (  # noqa: E402
    PRESENTATION_SYSTEM_PROMPT,
    PRESENTATION_TOOL_CHAR_CAP,
    run_agent,
)

SCENARIOS = ROOT / "presentation" / "scenarios.json"
OUT = ROOT / "outputs" / "presentation"
LABELS = ("HOLD", "WATCH", "INVESTIGATE", "POTENTIAL_CATCH_UP_CANDIDATE",
          "TECHNICAL_REVERSAL_CANDIDATE", "FUNDAMENTAL_IMPROVEMENT_CANDIDATE",
          "REJECT_SIGNAL", "ANALYSIS_UNSAFE")


def detected_label(answer: str) -> str | None:
    """Last of the 8 labels mentioned in the answer (the model is asked to end with it)."""
    best, pos = None, -1
    for label in LABELS:
        i = (answer or "").rfind(label)
        if i > pos:
            best, pos = label, i
    return best


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(ids: list[str] | None, model: str | None) -> None:
    spec = json.loads(SCENARIOS.read_text(encoding="utf-8"))
    d = spec["defaults"]
    (OUT / "traces").mkdir(parents=True, exist_ok=True)
    for sc in spec["scenarios"]:
        if ids and sc["id"] not in ids:
            continue
        path = OUT / "traces" / f"{sc['id']}.trace.json"
        print(f"[{sc['id']}] {sc['title']} ...", flush=True)
        result = run_agent(sc["question"], model=model or d["model"], seed=d["seed"],
                           temperature=d["temperature"], config=d["config"],
                           retrieval_top_k=d["rag_top_k"], max_turns=d["max_turns"],
                           system_prompt=PRESENTATION_SYSTEM_PROMPT, tool_char_cap=PRESENTATION_TOOL_CHAR_CAP, tool_schemas=False, scenario_id=sc["id"],
                           trace_path=path,
                           on_event=lambda kind, name, args: kind == "tool" and print(
                               f"    -> {name} {json.dumps(args, ensure_ascii=False)}", flush=True))
        t = result["execution_trace"]
        print(f"    done in {t['wall_time_s']}s, label={detected_label(t['final_answer'])}, "
              f"grounded={t['grounding_audit']['all_grounded']}", flush=True)
    write_index(spec)


def write_index(spec: dict) -> None:
    rows = []
    for sc in spec["scenarios"]:
        path = OUT / "traces" / f"{sc['id']}.trace.json"
        if not path.exists():
            continue
        t = json.loads(path.read_text(encoding="utf-8"))
        rows.append({"id": sc["id"], "scenario": sc["scenario"], "title": sc["title"],
                     "question": sc["question"], "trace": path.relative_to(ROOT).as_posix(),
                     "sha256": sha256_file(path), "run_id": t["run_id"],
                     "started_at": t["started_at"], "wall_time_s": t["wall_time_s"],
                     "model": t["model"].get("name"), "model_digest": t["model"].get("digest"),
                     "seed": t["sampling"]["seed"], "temperature": t["sampling"]["temperature"],
                     "tools_called": t["tools_called"], "label": detected_label(t["final_answer"]),
                     "all_grounded": t["grounding_audit"]["all_grounded"],
                     "ungrounded": [f["text"] for f in t["grounding_audit"]["ungrounded"]]})
    index = {"generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
             "scenarios_file": SCENARIOS.relative_to(ROOT).as_posix(),
             "scenarios_sha256": sha256_file(SCENARIOS), "traces": rows}
    (OUT / "index.json").write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")
    render_html(rows)
    print(f"index: {(OUT / 'index.json').relative_to(ROOT)}  html: {(OUT / 'traces.html').relative_to(ROOT)}")


def _pre(obj) -> str:
    text = obj if isinstance(obj, str) else json.dumps(obj, indent=2, ensure_ascii=False, default=str)
    if len(text) > 6000:
        text = text[:6000] + f"\n... [{len(text) - 6000} more chars in the JSON trace]"
    return f"<pre>{html.escape(text)}</pre>"


def render_html(rows: list[dict]) -> None:
    parts = []
    for row in rows:
        t = json.loads((ROOT / row["trace"]).read_text(encoding="utf-8"))
        m, s = t["model"], t["sampling"]
        steps = []
        for st in t["steps"]:
            if st["type"] == "tool_call":
                steps.append(f"<details><summary><b>{html.escape(st['tool'])}</b> "
                             f"<span class=m>[{st['actor']}] {html.escape(json.dumps(st['arguments'], ensure_ascii=False))}"
                             f" · {st['started_at']} · {st['duration_s']}s</span></summary>"
                             f"{_pre(st['result'])}</details>")
            elif st["type"] == "assistant":
                calls = ", ".join(c["name"] for c in st["tool_calls"]) or "final answer"
                steps.append(f"<div class=a><span class=m>turn {st['turn']} · model · {st['started_at']}"
                             f" · {st['duration_s']}s → {html.escape(calls)}</span>"
                             f"{_pre(st['content']) if st['content'] else ''}</div>")
            else:
                steps.append(f"<div class=h><span class=m>harness ({st['reason']}): "
                             f"{html.escape(st['content'])}</span></div>")
        g = t["grounding_audit"]
        parts.append(f"""
<section id="{row['id']}"><h2>{row['id']} · {html.escape(row['title'])}</h2>
<p class=q>{html.escape(t['user_prompt'])}</p>
<table>
<tr><th>Model</th><td>{html.escape(str(m.get('name')))} · digest {html.escape(str(m.get('digest'))[:19])}… · {m.get('family')} {m.get('parameter_size')} {m.get('quantization_level')} · Ollama {m.get('ollama_version')}</td></tr>
<tr><th>Sampling</th><td>temperature {s['temperature']} · seed {s['seed']} · top_p {s['top_p']} · num_ctx {s['num_ctx']}</td></tr>
<tr><th>Time</th><td>{t['started_at']} → {t['finished_at']} ({t['wall_time_s']} s)</td></tr>
<tr><th>Tools called</th><td>{html.escape(', '.join(t['tools_called']) or '—')}</td></tr>
<tr><th>Grounding</th><td>{g['grounded_count']} figures traced to tool output · ungrounded: {html.escape(', '.join(f['text'] for f in g['ungrounded']) or 'none')}</td></tr>
<tr><th>Trace file</th><td><code>{row['trace']}</code> · sha256 <code>{row['sha256'][:16]}…</code></td></tr>
</table>
<h3>Final answer</h3><div class=ans>{_pre(t['final_answer'])}</div>
<details><summary>System prompt</summary>{_pre(t['system_prompt'])}</details>
<details><summary>User message sent (question + retrieved context)</summary>{_pre(t['user_message_sent'])}</details>
<h3>Execution steps</h3>{''.join(steps)}
</section>""")
    doc = f"""<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1"><title>BIST agent — scenario traces</title>
<style>
body{{font:15px/1.5 system-ui,sans-serif;max-width:1100px;margin:2rem auto;padding:0 1rem;color:#1d232b}}
h2{{border-top:2px solid #1d232b;padding-top:1rem}} .q{{font-size:1.05rem;background:#f1f4f8;padding:.7rem 1rem;border-left:4px solid #2b5c8a}}
table{{border-collapse:collapse;width:100%;font-size:.9rem}} th{{text-align:left;width:9rem;color:#555;vertical-align:top}} td,th{{padding:.25rem .5rem;border-bottom:1px solid #e3e6ea}}
pre{{white-space:pre-wrap;word-break:break-word;background:#fafbfc;border:1px solid #e3e6ea;padding:.6rem;font-size:.82rem;max-height:28rem;overflow:auto}}
.ans pre{{background:#fff;border-color:#2b5c8a;font-size:.92rem}} .m{{color:#555;font-size:.85rem}} details{{margin:.3rem 0}} summary{{cursor:pointer}}
.a,.h{{margin:.4rem 0}} .h .m{{color:#8a5a00}}
</style></head><body>
<h1>BIST research agent: execution traces for the five scenarios</h1>
<p>Each answer below was produced by the local model through <code>scripts/local_agent.py</code>. Every figure is checked against the tool outputs (grounding audit), and the answer text is never edited.</p>
<nav>{' · '.join(f'<a href="#{r["id"]}">{r["id"]} {html.escape(r["title"])}</a>' for r in rows)}</nav>
{''.join(parts)}</body></html>"""
    (OUT / "traces.html").write_text(doc, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", nargs="*", help="Scenario ids to run (default: all).")
    parser.add_argument("--model", default=None, help="Override the model in scenarios.json.")
    parser.add_argument("--render-only", action="store_true")
    args = parser.parse_args()
    if args.render_only:
        write_index(json.loads(SCENARIOS.read_text(encoding="utf-8")))
    else:
        run(args.only, args.model)


if __name__ == "__main__":
    main()
