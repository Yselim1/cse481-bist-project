"""Base vs fine-tuned comparison on the 20-question §30 eval, under both agent protocols.

Reads (written by training/eval/run_baseline.py):
    outputs/harness/eval_v3/{base,finetuned}.{original,presentation}.score.json
    outputs/harness/{base_3b,baseline_local}.score.json   (earlier v1 fine-tune, for reference)
Writes:
    outputs/training/base_vs_finetuned.md
    outputs/harness/eval_v3/summary.json                  (read by scripts/generate_deliverables.py)
    outputs/training/figures/base_vs_finetuned{,_dark}.png

    .\\.venv\\Scripts\\python.exe training/eval/compare.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVAL = ROOT / "outputs" / "harness" / "eval_v3"
OUT_MD = ROOT / "outputs" / "training" / "base_vs_finetuned.md"
FIG_DIR = ROOT / "outputs" / "training" / "figures"

METRICS = [  # key, lower_is_better, short label
    ("invalid_tool_call_rate", True, "invalid tool call"),
    ("missing_required_tool_rate", True, "missing required tool"),
    ("label_mismatch_rate", True, "label mismatch"),
    ("advice_leak_rate", True, "advice leak"),
    ("unknown_label_emitted_rate", True, "unknown label token"),
    ("ungrounded_answer_rate", True, "ungrounded figure"),
    ("max_turns_exceeded_rate", True, "no answer (turn limit)"),
    ("reproducibility_rate", False, "non-empty answer"),
]
PROTOCOLS = {
    "original": "Original eval protocol: Ollama sends the 21 tool schemas, base system prompt, "
                "12 KB tool-result cap, no RAG (same settings as the earlier v1 evaluation).",
    "presentation": "Presentation protocol: no schemas (the model writes `<tool_call>` text, as in "
                    "its fine-tuning data), presentation system prompt, RAG context, 4.5 KB cap; "
                    "the settings of `scripts/ask.py` and the five scenario traces.",
}
BASE_COLOR, TUNED_COLOR = "#e76624", "#338ced"  # validated: dataviz validate_palette.js, dark


def _load(path: Path) -> dict | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def _verdict(base: float, tuned: float, lower_better: bool) -> str:
    if abs(tuned - base) < 1e-9:
        return "tie"
    return "improved" if (tuned < base) == lower_better else "regressed"


def _rate(v) -> str:
    return f"{v:.2f}" if isinstance(v, (int, float)) else "n/a"


def _chart(summary: dict, dark: bool) -> Path:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    surface, ink, muted, grid = (("#16213e", "#e8e8f0", "#9c9cb0", "#2a3558") if dark
                                 else ("#ffffff", "#191919", "#666666", "#e6e6e6"))
    protos = [p for p in PROTOCOLS if p in summary["protocols"]]
    fig, axes = plt.subplots(1, len(protos), figsize=(6.4 * len(protos), 5.4), sharey=True,
                             facecolor=surface)
    axes = axes if len(protos) > 1 else [axes]
    labels = [f"{lab}  ({'↓' if low else '↑'} better)" for _, low, lab in METRICS]
    y = range(len(METRICS))
    h = 0.36
    for ax, proto in zip(axes, protos):
        rows = summary["protocols"][proto]["metrics"]
        ax.set_facecolor(surface)
        for offset, who, color in ((-h / 2 - 0.01, "base", BASE_COLOR), (h / 2 + 0.01, "finetuned", TUNED_COLOR)):
            vals = [rows[k][who] for k, _, _ in METRICS]
            ax.barh([i + offset for i in y], vals, height=h, color=color, edgecolor=surface,
                    linewidth=1, label=summary["models"][who])
            for i, v in enumerate(vals):
                ax.text(v + 0.015, i + offset, f"{v:.2f}", va="center", ha="left",
                        fontsize=8, color=muted)
        ax.set_xlim(0, 1.12)
        ax.set_title({"original": "Original eval protocol (tool schemas)",
                      "presentation": "Presentation protocol (training format + RAG)"}[proto],
                     color=ink, fontsize=11, loc="left")
        ax.tick_params(colors=muted, labelsize=9, length=0)
        ax.grid(axis="x", color=grid, linewidth=0.8)
        ax.set_axisbelow(True)
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
        ax.spines["bottom"].set_color(grid)
        ax.set_xlabel("share of the 20 questions", color=muted, fontsize=9)
    axes[0].set_yticks(list(y))
    axes[0].set_yticklabels(labels, color=ink, fontsize=9)
    axes[0].invert_yaxis()
    handles, names = axes[0].get_legend_handles_labels()
    fig.legend(handles, names, loc="upper right", ncol=2, frameon=False, labelcolor=ink, fontsize=9)
    fig.suptitle("Base vs fine-tuned Qwen 2.5 3B — 20-question §30 eval", color=ink, fontsize=13,
                 x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    path = FIG_DIR / f"base_vs_finetuned{'_dark' if dark else ''}.png"
    fig.savefig(path, dpi=160, facecolor=surface)
    plt.close(fig)
    return path


def main() -> None:
    summary: dict = {"models": {}, "protocols": {}, "source_dir": EVAL.relative_to(ROOT).as_posix()}
    lines = ["# Base vs fine-tuned local LLM (§30 metrics)", ""]
    for proto, desc in PROTOCOLS.items():
        base = _load(EVAL / f"base.{proto}.score.json")
        tuned = _load(EVAL / f"finetuned.{proto}.score.json")
        if not base or not tuned:
            continue
        summary["models"] = {"base": base["model"], "finetuned": tuned["model"],
                             "base_digest": base.get("model_digest"),
                             "finetuned_digest": tuned.get("model_digest")}
        tally = {"improved": 0, "tie": 0, "regressed": 0}
        rows = {}
        table = ["| Metric | Direction | Base | Fine-tuned | Verdict |", "|---|---|---|---|---|"]
        for key, low, _ in METRICS:
            b, t = base.get(key, 0.0), tuned.get(key, 0.0)
            v = _verdict(b, t, low)
            tally[v] += 1
            rows[key] = {"base": b, "finetuned": t, "verdict": v, "lower_is_better": low}
            table.append(f"| `{key}` | {'↓' if low else '↑'} | {_rate(b)} | {_rate(t)} | {v} |")
        by_id = {e["id"]: e for e in base["entries"]}
        qrows = ["| Q | Scenario | Expected label | Base label | Fine-tuned label | Fine-tuned tools |",
                 "|---|---|---|---|---|---|"]
        for e in tuned["entries"]:
            be = by_id.get(e["id"], {})
            qrows.append(f"| {e['id']} | {e.get('scenario')} | {e.get('label_expected') or '—'} | "
                         f"{be.get('label_detected') or '—'} | {e.get('label_detected') or '—'} | "
                         f"{', '.join(e.get('tools_called') or []) or '—'} |")
        summary["protocols"][proto] = {"description": desc, "metrics": rows, "tally": tally,
                                       "mean_wall_time_s": {
                                           "base": round(sum(x.get("wall_time_s") or 0 for x in base["entries"]) / len(base["entries"]), 1),
                                           "finetuned": round(sum(x.get("wall_time_s") or 0 for x in tuned["entries"]) / len(tuned["entries"]), 1)}}
        lines += [f"## {proto.capitalize()} protocol", "", desc, "",
                  f"**Fine-tuned vs base: {tally['improved']} improved, {tally['tie']} tied, "
                  f"{tally['regressed']} regressed** (of {len(METRICS)} metrics).", "",
                  *table, "", "<details><summary>Per-question labels</summary>", "", *qrows, "",
                  "</details>", ""]

    v1_base, v1_tuned = (_load(ROOT / "outputs/harness/base_3b.score.json"),
                         _load(ROOT / "outputs/harness/baseline_local.score.json"))
    if v1_base and v1_tuned and "original" in summary["protocols"]:
        cur = summary["protocols"]["original"]["metrics"]
        lines += ["## Earlier fine-tune (v1) for reference", "",
                  "Same 20 questions and original protocol; the v1 adapter was trained on dataset v1 "
                  "and is not part of the submission. v1 numbers are as recorded at the time, before "
                  "the unknown-label tokenizer fix, so their unknown-label rates are overstated.", "",
                  "| Metric | Base (Ollama default ctx) | v1 fine-tune | v3 fine-tune (submitted) |",
                  "|---|---|---|---|"]
        for key, _, _ in METRICS[:5] + METRICS[7:]:
            lines.append(f"| `{key}` | {_rate(v1_base.get(key))} | {_rate(v1_tuned.get(key))} | "
                         f"{_rate(cur[key]['finetuned'])} |")
        lines.append("")
        summary["v1_reference"] = {k: {"base": v1_base.get(k), "finetuned_v1": v1_tuned.get(k)}
                                   for k, _, _ in METRICS if k in v1_base}

    notes = ROOT / "outputs" / "training" / "base_vs_finetuned.notes.md"
    if notes.exists():
        lines += [notes.read_text(encoding="utf-8").rstrip(), ""]
    lines += ["## Metric definitions", "",
              "- `invalid_tool_call_rate`: share of questions where at least one MCP call returned an error.",
              "- `missing_required_tool_rate`: share missing at least one tool from the question's plan.",
              "- `label_mismatch_rate`: share whose label is outside the expected set (questions without "
              "an expected label pass vacuously).",
              "- `advice_leak_rate`: share containing banned advisory phrases.",
              "- `unknown_label_emitted_rate`: share emitting an UPPER_SNAKE token outside the 8 labels "
              "(also catches quoted tool identifiers such as BB_LOWER_TOUCH).",
              "- `ungrounded_answer_rate`: share whose answer contains a figure the grounding audit could "
              "not trace to a tool output (`src/bist_analytics/harness/grounding.py`).",
              "- `max_turns_exceeded_rate`: share that hit the 15-turn limit without an answer.",
              "- `reproducibility_rate`: share producing a non-empty final answer.", "",
              "Both models: temperature 0, seed 17, 16k context (`training/Modelfile.base` builds "
              "`bist-qwen-base` from `qwen2.5:3b-instruct` with the fine-tune's context and sampling "
              "settings). Per-question traces: `outputs/harness/eval_v3/traces/`. "
              "Chart: `outputs/training/figures/base_vs_finetuned.png`."]
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    (EVAL / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    figs = [_chart(summary, dark) for dark in (False, True)] if summary["protocols"] else []
    print(json.dumps({p: v["tally"] for p, v in summary["protocols"].items()}),
          *[f.relative_to(ROOT).as_posix() for f in figs])


if __name__ == "__main__":
    main()
