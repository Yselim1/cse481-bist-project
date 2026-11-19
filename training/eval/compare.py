"""Compare base-vs-fine-tuned baseline evals and write a §30-metrics table.

Reads:  outputs/harness/base.score.json, outputs/harness/finetuned.score.json
Writes: outputs/training/base_vs_finetuned.md
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

METRICS = [
    ("invalid_tool_call_rate", "lower_is_better"),
    ("missing_required_tool_rate", "lower_is_better"),
    ("label_mismatch_rate", "lower_is_better"),
    ("advice_leak_rate", "lower_is_better"),
    ("unknown_label_emitted_rate", "lower_is_better"),
    ("reproducibility_rate", "higher_is_better"),
]


def _format(value: float) -> str:
    return f"{value:.3f}" if isinstance(value, (int, float)) else "n/a"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default=str(ROOT/"outputs/harness/base.score.json"))
    parser.add_argument("--finetuned", default=str(ROOT/"outputs/harness/finetuned.score.json"))
    parser.add_argument("--output", default=str(ROOT/"outputs/training/base_vs_finetuned.md"))
    args = parser.parse_args()

    base = json.loads(Path(args.base).read_text(encoding="utf-8"))
    tuned = json.loads(Path(args.finetuned).read_text(encoding="utf-8"))

    improved = 0
    regressed = 0
    rows = ["| Metric | Direction | Base | Fine-tuned | Δ | Verdict |",
            "|---|---|---|---|---|---|"]
    for key, direction in METRICS:
        b = base.get(key)
        t = tuned.get(key)
        delta = (t - b) if isinstance(b, (int, float)) and isinstance(t, (int, float)) else None
        verdict = "n/a"
        if delta is not None:
            better = delta < 0 if direction == "lower_is_better" else delta > 0
            if abs(delta) < 1e-6:
                verdict = "tie"
            elif better:
                verdict = "improved"
                improved += 1
            else:
                verdict = "regressed"
                regressed += 1
        rows.append(f"| {key} | {direction} | {_format(b)} | {_format(t)} | "
                    f"{_format(delta) if delta is not None else 'n/a'} | {verdict} |")

    lines = [
        "# Base vs fine-tuned local LLM (§30 metrics)",
        "",
        f"- Base model: `{base.get('model', 'unknown')}`",
        f"- Fine-tuned model: `{tuned.get('model', 'unknown')}`",
        f"- Questions: {base.get('total_questions')} baseline + {tuned.get('total_questions')} held-out replay",
        f"- Improved on {improved} / {len(METRICS)} axes; regressed on {regressed}.",
        "",
        *rows,
        "",
        "## Reading guide",
        "",
        "- `invalid_tool_call_rate` — share of questions where at least one tool call errored out.",
        "- `missing_required_tool_rate` — share of questions missing at least one tool from the plan.",
        "- `label_mismatch_rate` — share where the committed educational label does not match the expected label (or label set).",
        "- `advice_leak_rate` — share of answers containing banned advisory phrasing.",
        "- `unknown_label_emitted_rate` — share emitting labels outside the frozen 8-label set.",
        "- `reproducibility_rate` — share producing a non-empty final answer (schema-shaped).",
        "",
        "## Interpretation",
        "",
        "A pass requires improvement on ≥3 of the 6 axes; honest documentation of any regression is "
        "acceptable per plan D6. See `docs/MODEL_CARD.md` for the training config and known limitations.",
    ]
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {args.output} — improved {improved}/{len(METRICS)}, regressed {regressed}/{len(METRICS)}")


if __name__ == "__main__":
    main()
