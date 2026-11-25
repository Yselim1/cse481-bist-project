r"""Ask the local BIST agent any question. This is the CLI for the live classroom question.

    .\.venv\Scripts\python.exe scripts/ask.py "Is PGSUS.IS lagging the airline sector as of 2025-09-30?"

It uses the same code path, system prompt, seed, temperature, config and RAG settings as
the five pre-run scenarios (``presentation/scenarios.json`` defaults). Tool calls are
printed as they happen, then the final answer and the grounding audit. The full execution
trace is saved under ``outputs/presentation/live/``.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.local_agent import PRESENTATION_SYSTEM_PROMPT, run_agent  # noqa: E402

DEFAULTS = json.loads((ROOT / "presentation" / "scenarios.json").read_text(encoding="utf-8"))["defaults"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("question")
    parser.add_argument("--model", default=DEFAULTS["model"])
    parser.add_argument("--seed", type=int, default=DEFAULTS["seed"])
    parser.add_argument("--temperature", type=float, default=DEFAULTS["temperature"])
    parser.add_argument("--config", default=DEFAULTS["config"])
    parser.add_argument("--rag-top-k", type=int, default=DEFAULTS["rag_top_k"])
    parser.add_argument("--max-turns", type=int, default=DEFAULTS["max_turns"])
    args = parser.parse_args()

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = ROOT / "outputs" / "presentation" / "live" / f"{stamp}.trace.json"
    t0 = time.perf_counter()

    def on_event(kind: str, name, payload) -> None:
        elapsed = f"{time.perf_counter() - t0:6.1f}s"
        if kind == "thinking":
            print(f"[{elapsed}] model turn {name} ...", flush=True)
        elif kind == "tool":
            print(f"[{elapsed}]   tool {name} {json.dumps(payload, ensure_ascii=False)}", flush=True)

    print(f"model={args.model} seed={args.seed} temperature={args.temperature} config={args.config}")
    result = run_agent(args.question, model=args.model, seed=args.seed, temperature=args.temperature,
                       config=args.config, retrieval_top_k=args.rag_top_k, max_turns=args.max_turns,
                       system_prompt=PRESENTATION_SYSTEM_PROMPT, scenario_id="LIVE",
                       trace_path=path, on_event=on_event)
    t = result["execution_trace"]
    g = t["grounding_audit"]
    print("\n" + "=" * 78 + "\nFINAL ANSWER\n" + "=" * 78)
    print(t["final_answer"])
    print("=" * 78)
    print(f"tools called : {', '.join(t['tools_called']) or '-'}")
    print(f"grounding    : {g['grounded_count']} figures traced to tool output; "
          f"ungrounded: {', '.join(f['text'] for f in g['ungrounded']) or 'none'}")
    if not g["all_grounded"]:
        print("WARNING      : some figures in the answer were not found in any tool output.")
    print(f"wall time    : {t['wall_time_s']} s")
    print(f"trace        : {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
