#!/usr/bin/env python3
r"""Generate three submission deliverables for CSE481 term project.

Outputs (in outputs/deliverables/):
  requirements_report.pdf  - requirements-vs-done compliance report
  presentation_slides.html - 12-slide deck (open in browser; Ctrl+P to PDF)
  qa_prep.pdf              - anticipated instructor Q&A with model answers

Usage:
    .\.venv\Scripts\python.exe scripts/generate_deliverables.py
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from reportlab.platypus import Paragraph, TableStyle

ROOT =Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "outputs" / "deliverables"

# ── colour palette (shared) ───────────────────────────────────────────────────
_NAVY_HEX  = "#1a1a2e"
_BLUE_HEX  = "#0f3460"
_RED_HEX   = "#e94560"
_GREEN_HEX = "#2e8b57"
_AMBER_HEX = "#c97000"
_LGREY_HEX = "#f7f7f7"
_MGREY_HEX = "#cccccc"


# ─────────────────────────────────────────────────────────────────────────────
#  Facts: every model-related number is read from the result files, not typed in
# ─────────────────────────────────────────────────────────────────────────────

def _read_json(rel: str) -> dict:
    import json
    path = ROOT / rel
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _scenario_key_figures(trace: dict) -> str:
    """One-line summary of the figures the model reported, taken from the tool output the
    model saw (so the slide shows tool values, never values typed by hand)."""
    calls = [s for s in trace.get("steps", []) if s.get("type") == "tool_call" and s.get("actor") != "harness"]
    if not calls:
        return "no tool call"
    res = calls[0].get("result") or {}
    sc = res.get("structuredContent") or {}
    tool = calls[0]["tool"]
    if res.get("isError"):
        import re
        text = " ".join(c.get("text", "") for c in res.get("content", []))
        m = re.search(r"\b([A-Z][A-Z_]{5,}): (.*?)(?:;|$)", text)
        return f"tool error {m.group(1)}: {m.group(2)}" if m else "tool error"
    if tool == "rank_sector_relative_strength":
        sm = next((x for x in sc.get("sector_summary", []) if x["sector"] == "banking"), None)
        return (f"banking laggard {sm['laggard']} {sm['laggard_relative_vs_sector']:+.4f} vs sector"
                if sm else "")
    if tool == "test_weekday_pattern":
        s = sc.get("summary", {})
        return (f"highest {s['highest_mean_weekday']} {s['highest_mean']:+.6f}, lowest "
                f"{s['lowest_mean_weekday']} {s['lowest_mean']:+.6f}, smallest p {s['smallest_p_value']:.3f}")
    if tool == "detect_reversal_events":
        b = sc.get("best_family", {})
        return (f"{sc.get('event_count')} events; best {b.get('event_type')} "
                f"mean 5-day {b.get('mean_forward_5d'):+.4f}")
    if tool == "calculate_fundamental_change":
        d = sc.get("data", {})
        r = d.get("publication_reaction", {})
        return (f"revenue qoq {d.get('revenue_qoq'):+.4f}, net profit qoq {d.get('net_profit_qoq'):+.4f}; "
                f"published {str(d.get('financial_available_at'))[:10]}; 5-session reaction "
                f"{r.get('return_5_sessions'):+.4f}")
    return ""


def _facts() -> dict:
    import json
    import re

    import yaml

    hp = _read_json("training/config/hyperparams.json")
    audit = _read_json("training/dataset/audit.json")
    live = yaml.safe_load((ROOT / "config/universe_live.yaml").read_text(encoding="utf-8"))
    kb = _read_json("rag/knowledge_base.json")
    sub = _read_json("submission.json")
    gguf = (sub.get("served_model") or {}).get("gguf") or {}
    server = (ROOT / "src/bist_analytics/mcp/server.py").read_text(encoding="utf-8")
    index = _read_json("outputs/presentation/index.json")
    scen = json.loads((ROOT / "presentation/scenarios.json").read_text(encoding="utf-8"))
    scenarios = []
    for row in index.get("traces", []):
        trace = _read_json(row["trace"])
        q = next((s for s in scen["scenarios"] if s["id"] == row["id"]), {})
        scenarios.append({**row, "title": q.get("title", row["scenario"]),
                          "wall_time_s": trace.get("wall_time_s"),
                          "key": _scenario_key_figures(trace)})
    built = audit.get("scenarios_built", {})
    return {
        "tools": len(re.findall(r"@server\.tool\(", server)),
        "tickers": len(live["universe"]), "sectors": len(set(live["sector_map"].values())),
        "sector_names": sorted(set(live["sector_map"].values())),
        "kb_docs": kb.get("document_count"),
        "train_min": round((hp.get("train_seconds") or 0) / 60),
        "eval_loss": (hp.get("results") or {}).get("eval", {}).get("eval_loss"),
        "train_loss": (hp.get("results") or {}).get("train_loss"),
        "steps": (hp.get("results") or {}).get("global_steps"),
        "hyper": hp.get("hyperparameters", {}), "env": hp.get("environment", {}),
        "base": hp.get("base_model", {}), "adapter_sha": (hp.get("adapter") or {}).get("sha256", ""),
        "dataset_rows": (hp.get("dataset") or {}),
        "gguf_gb": round(gguf.get("bytes", 0) / 1e9, 1),
        "served_digest": (sub.get("served_model") or {}).get("digest", ""),
        "built": built, "total_examples": sum(built.values()),
        "natural_share": audit.get("natural_share"),
        "held_out": audit.get("held_out_presentation_settings", []),
        "scenarios": scenarios,
        "eval": _read_json("outputs/harness/eval_v3/summary.json"),
        "harness": _read_json("outputs/harness/comparison.finetuned.json"),
        "harness_base": _read_json("outputs/harness/comparison.base.json"),
    }


F: dict = {}  # filled in main()

EVAL_READING = (
    "On the presentation protocol the base model never calls a tool and 7 of its 20 answers "
    "contain figures no tool returned; the fine-tune calls the planned tool in 19 of 20 and has "
    "one ungrounded answer. With Ollama's tool schemas the base is the stronger agent: the "
    "fine-tune, trained without schemas, chains extra tools (invalid-call rate 0.45). The "
    "fine-tune is over-cautious outside its five question types: 11 of 20 answers say "
    "ANALYSIS_UNSAFE although only 2 questions are unsafe cases. Remaining unknown-label hits are "
    "gate and error codes quoted from tools (HARD_BLOCK, INVALID_SYMBOL). Details: "
    "outputs/training/base_vs_finetuned.md."
)
HARNESS_READING = (
    "Same THYAO question through each stage; only the architecture changes. For both models, "
    "adding tools (A→B) takes evidence_coverage and workflow_completion from 0 to 1.0. The "
    "fine-tune keeps constraint_compliance in all 5 stages (base: 2 of 5) and passes the as_of "
    "and context_event checks in every tool stage; numeric_exactness stays 0 for both on this "
    "11-field question. Base results: outputs/harness/comparison.base.json."
)
LIMITATIONS_TEXT = [
    "<b>A 3B model reads rather than reasons.</b> Correct answers depend on the tools doing the "
    "comparisons (sector_summary, best_family, label_by_rule). In one dry run on an 8-sector "
    "output the label was right but the explanation quoted another sector's figures.",
    "<b>Grounding is not attribution.</b> The audit proves each figure appears in a tool output; "
    "it cannot prove the figure is attached to the right ticker.",
    "<b>Over-cautious outside its five question types.</b> On the 20-question eval it labelled 11 "
    "answers ANALYSIS_UNSAFE although only 2 were unsafe cases, and once applied the gate wrongly "
    "(gate said INVESTIGATE). It does not know tools it was not trained on (asked to call "
    "project_status, it called check_data_quality).",
    "<b>Works only in its own tool format.</b> Trained without tool schemas; when Ollama sends the "
    "21 schemas it chains extra tools (invalid-call rate 0.45 vs 0.05 for the base). The "
    "presentation path therefore uses the training format.",
    "<b>Fundamentals for THYAO only; TMS 29 boundary.</b> Other tickers return available=false "
    "and the model labels INVESTIGATE rather than estimating. Pre/post-TMS 29 statements are "
    "never mixed (PERIOD_MISMATCH is hard-blocked).",
    "<b>Evaluator and safety limits.</b> Only 4 of the 20 eval questions expect a particular label, so label "
    "accuracy rests on four answers; the unknown-label metric also counts quoted tool codes. "
    "No RLHF: 'no investment advice' rests on the prompt, the 8 labels and the data-quality gate.",
]

LIMITATIONS_SLIDE = """\
<div class="tag">Limitations</div>
<h1>Honest Limitations</h1>
<div class="cols" style="margin-top:1rem">
  <div>
    <div class="card" style="margin-bottom:0.8rem">
      <h3>1. A 3B Model Reads, It Does Not Reason</h3>
      <p>Correct answers depend on the tools doing the comparisons. In one dry run on an
         8-sector output, the label was right but the explanation quoted another sector's figures.</p>
    </div>
    <div class="card" style="margin-bottom:0.8rem">
      <h3>2. Grounding ≠ Attribution</h3>
      <p>The audit proves each figure exists in a tool output; it cannot prove the figure is
         attached to the right ticker. Sector answers need a human read.</p>
    </div>
    <div class="card">
      <h3>3. Over-Cautious Outside Its 5 Question Types</h3>
      <p>On the 20-question eval: 11 answers say ANALYSIS_UNSAFE, only 2 should. It doesn't know
         tools it wasn't trained on (asked for <code>project_status</code>, it ran the quality gate).</p>
    </div>
  </div>
  <div>
    <div class="card" style="margin-bottom:0.8rem">
      <h3>4. Works Only in Its Own Tool Format</h3>
      <p>Trained without tool schemas; given Ollama's 21 schemas it chains extra tools
         (invalid calls 0.45 vs 0.05 for the base). The presentation path uses the training format.</p>
    </div>
    <div class="card" style="margin-bottom:0.8rem">
      <h3>5. Fundamentals for THYAO Only</h3>
      <p>Other tickers return <code>available: false</code> and get INVESTIGATE. Pre/post-TMS 29
         statements are never mixed (PERIOD_MISMATCH hard-block).</p>
    </div>
    <div class="card">
      <h3>6. Evaluator and Safety Limits</h3>
      <p>Only 4 of 20 eval questions expect a particular label. No RLHF: "no advice" rests on the
         prompt, the 8 labels and the quality gate.</p>
    </div>
  </div>
</div>"""


def _pct(v) -> str:
    return f"{v:.2f}" if isinstance(v, (int, float)) else "n/a"


# ─────────────────────────────────────────────────────────────────────────────
#  PDF helpers
# ─────────────────────────────────────────────────────────────────────────────

def _pdf_styles():
    """Return a dict of named ParagraphStyle objects."""
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet

    ss = getSampleStyleSheet()
    navy = colors.HexColor(_NAVY_HEX)
    blue = colors.HexColor(_BLUE_HEX)

    return {
        "cover_title": ParagraphStyle(
            "cover_title", parent=ss["Title"],
            fontSize=22, spaceAfter=14, textColor=navy, alignment=TA_CENTER,
        ),
        "cover_sub": ParagraphStyle(
            "cover_sub", parent=ss["Normal"],
            fontSize=12, spaceAfter=8, textColor=colors.HexColor("#555555"),
            alignment=TA_CENTER,
        ),
        "cover_meta": ParagraphStyle(
            "cover_meta", parent=ss["Normal"],
            fontSize=10, spaceAfter=6, textColor=colors.HexColor("#888888"),
            alignment=TA_CENTER,
        ),
        "h1": ParagraphStyle(
            "h1", parent=ss["Heading1"],
            fontSize=13, spaceBefore=18, spaceAfter=8, textColor=navy,
        ),
        "h2": ParagraphStyle(
            "h2", parent=ss["Heading2"],
            fontSize=11, spaceBefore=12, spaceAfter=6, textColor=blue,
        ),
        "body": ParagraphStyle(
            "body", parent=ss["Normal"],
            fontSize=9, spaceAfter=5, leading=13,
        ),
        "note": ParagraphStyle(
            "note", parent=ss["Normal"],
            fontSize=7.5, leading=10, textColor=colors.HexColor("#555555"),
            spaceAfter=4, leftIndent=8,
        ),
        "cell": ParagraphStyle(
            "cell", parent=ss["Normal"],
            fontSize=8, leading=10,
        ),
        "cell_bold": ParagraphStyle(
            "cell_bold", parent=ss["Normal"],
            fontSize=8, leading=10, fontName="Helvetica-Bold",
        ),
        "cell_hdr": ParagraphStyle(
            "cell_hdr", parent=ss["Normal"],
            fontSize=8.5, leading=11, fontName="Helvetica-Bold",
            textColor=colors.white,
        ),
        "q": ParagraphStyle(
            "q", parent=ss["Normal"],
            fontSize=10, spaceBefore=16, spaceAfter=4,
            fontName="Helvetica-Bold", textColor=blue,
        ),
        "a": ParagraphStyle(
            "a", parent=ss["Normal"],
            fontSize=9, spaceAfter=6, leading=13, leftIndent=10,
        ),
    }


def _table_style(row_count: int, hdr_rows: int = 1) -> "TableStyle":
    from reportlab.lib import colors
    from reportlab.platypus import TableStyle

    navy = colors.HexColor(_NAVY_HEX)
    lgrey = colors.HexColor(_LGREY_HEX)
    mgrey = colors.HexColor(_MGREY_HEX)

    cmds = [
        ("GRID", (0, 0), (-1, -1), 0.3, mgrey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING",   (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 3),
    ]
    for r in range(hdr_rows):
        cmds += [
            ("BACKGROUND", (0, r), (-1, r), navy),
            ("TEXTCOLOR",  (0, r), (-1, r), colors.white),
        ]
    for i in range(hdr_rows, row_count + hdr_rows):
        if (i - hdr_rows) % 2 == 1:
            cmds.append(("BACKGROUND", (0, i), (-1, i), lgrey))
    return TableStyle(cmds)


def _status_cell(status: str, style) -> "Paragraph":
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Paragraph

    colour_map = {
        "PASS": _GREEN_HEX,
        "DONE": _GREEN_HEX,
        "AMBER": _AMBER_HEX,
        "FAIL": "#cc0000",
    }
    key = status.upper().split()[0]
    hex_c = colour_map.get(key, "#333333")
    styled = ParagraphStyle(
        f"stat_{key}", parent=style,
        textColor=colors.HexColor(hex_c),
        fontName="Helvetica-Bold",
    )
    return Paragraph(status, styled)


# ─────────────────────────────────────────────────────────────────────────────
#  DELIVERABLE 1 — Requirements Compliance Report
# ─────────────────────────────────────────────────────────────────────────────

def build_requirements_report(out: Path) -> None:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        HRFlowable,
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
    )

    W, H = A4  # 595 × 842 pt
    MARGIN = 2.2 * cm
    TW = W - 2 * MARGIN  # ~452 pt usable width

    doc = SimpleDocTemplate(
        str(out), pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=MARGIN,
        title="CSE481 Requirements Compliance Report",
        author="Yavuz Selim",
    )
    S = _pdf_styles()
    P = Paragraph
    story = []

    # ── Cover ─────────────────────────────────────────────────────────────────
    story += [
        Spacer(1, 2 * cm),
        P("CSE481 Engineering Economics", S["cover_sub"]),
        P("Term Project — Requirements Compliance Report", S["cover_title"]),
        HRFlowable(width=TW, thickness=2, color=_NAVY_HEX, spaceAfter=16),
        P("Yavuz Selim", S["cover_sub"]),
        P("November 2026", S["cover_meta"]),
        P("Model: <b>bist-qwen</b> (Qwen 2.5 3B + LoRA via Ollama)", S["cover_meta"]),
        Spacer(1, 1.5 * cm),
        P(
            "This report maps every instructor-stated requirement to concrete "
            "implementation evidence. Sources: the project PDF, instructorQA.txt "
            "project announcement, and the ACCEPTANCE.md audit in the codebase.",
            S["body"],
        ),
        PageBreak(),
    ]

    # ── Section 1 — Project Overview ──────────────────────────────────────────
    story += [
        P("1. Project Overview", S["h1"]),
        HRFlowable(width=TW, thickness=1, color=_NAVY_HEX, spaceAfter=8),
        P(
            "A locally-hosted fine-tuned LLM (Qwen 2.5 3B + LoRA) drives a BIST "
            f"financial-analysis agent over {F['tools']} MCP tools. All inference runs offline "
            "via Ollama (localhost:11434); no cloud AI calls are made. Every answer carries an "
            "execution trace and a grounding audit that traces each figure to a tool output.",
            S["body"],
        ),
        Spacer(1, 0.3 * cm),
    ]

    overview_data = [
        [P("Dimension", S["cell_hdr"]), P("Value", S["cell_hdr"])],
        [P("Tickers", S["cell"]),        P(f"{F['tickers']} on the agent path (config/universe_live.yaml); the 10-ticker "
                                           "sample (universe10) backs the four scenario reports", S["cell"])],
        [P("Sectors", S["cell"]),        P(" · ".join(x.capitalize() for x in F["sector_names"]), S["cell"])],
        [P("Fundamental data", S["cell"]), P("Fintables TMS29 (2025–2026), 238 verified observations", S["cell"])],
        [P("Context events", S["cell"]), P("13 KAP timestamped events + USD/TRY FX (central-bank/CPI macro reader built, no series cached)", S["cell"])],
        [P("MCP tools", S["cell"]),      P(f"{F['tools']} read-only tools (stdio transport), incl. BM25 knowledge-base search", S["cell"])],
        [P("RAG knowledge base", S["cell"]), P(f"{F['kb_docs']} documents with source metadata (rag/knowledge_base.json)", S["cell"])],
        [P("Training examples", S["cell"]), P(f"{F['total_examples']} grounding-checked SFT traces, dataset v3 (80/20 train/eval split)", S["cell"])],
        [P("Training method", S["cell"]), P(f"QLoRA rank 16 / alpha 32 on Colab {F['env'].get('gpu', 'T4')} "
                                            f"({F['train_min']} min, eval_loss {F['eval_loss']:.4f})", S["cell"])],
        [P("Harness stages", S["cell"]), P("5 (raw_llm → llm_tools → stateful → evidence_gate → memory_review)", S["cell"])],
        [P("Eval questions", S["cell"]), P("20 hand-curated questions, §30 metrics, two agent protocols", S["cell"])],
        [P("Presentation traces", S["cell"]), P("5 pre-run scenarios (outputs/presentation/traces), all figures grounded", S["cell"])],
        [P("Deployment", S["cell"]),     P("Ollama local tag bist-qwen; runs fully on a 4 GB laptop GPU; offline", S["cell"])],
    ]
    story.append(Table(overview_data, colWidths=[TW * 0.28, TW * 0.72],
                        style=_table_style(len(overview_data) - 1)))
    story.append(PageBreak())

    # ── Section 2 — Original PDF Requirements ─────────────────────────────────
    story += [
        P("2. Original PDF Requirements (R01–R19)", S["h1"]),
        HRFlowable(width=TW, thickness=1, color=_NAVY_HEX, spaceAfter=8),
    ]

    req_rows = [
        [P("ID / Requirement", S["cell_hdr"]), P("Status", S["cell_hdr"]), P("Concrete Evidence", S["cell_hdr"])],
        ["R01\nPython / reproducibility", "PASS",
         "src/, uv.lock, config/, README.md, executed notebook (9 cells, 0 errors); "
         "outputs/verification/reproduction.json confirms fresh-env match."],
        ["R02\nBIST100 company", "PASS",
         "THYAO.IS selected; data/raw/fintables/membership.json. Historical membership "
         "caveat disclosed in ACCEPTANCE.md."],
        ["R03\nStock/index OHLCV", "PASS",
         f"Yahoo Finance cache: {F['tickers']} tickers + XU100.IS, 1250+ sessions; "
         "three raw snapshots + quality.json. Missing prices not filled; calendar gaps disclosed."],
        ["R04\nTechnical indicators / volume", "PASS",
         "analysis/indicators.py: SMA, EMA, RSI, MACD, Bollinger, ATR, KAMA, Supertrend. "
         "Hand identities and prefix tests in test suite."],
        ["R05\nAutomatic support/resistance", "PASS",
         "analysis/levels.py: pivot clustering with right-window confirmation. "
         "pivots.csv, zones.csv; causal-prefix tests."],
        ["R06\nIncome statement", "PASS",
         "Revenue, gross profit, EBITDA, operating profit, net profit from Fintables. "
         "Original page 11 of 4 PDFs, 40 identities reconciled exactly."],
        ["R07\nBalance sheet", "PASS",
         "Cash, financial debt, net debt, assets, equity from Fintables. "
         "Original pages 9-10; documented formulas in DATA_DICTIONARY.md."],
        ["R08\nCash flow", "PASS",
         "Operating, investing, financing CF from Fintables original page 13. "
         "Cash-flow identities reconciled."],
        ["R09\nGrowth metrics", "PASS",
         "Revenue/EBITDA/earnings YoY growth; negative comparison bases unavailable "
         "(unavailable, not filled with zero) — disclosed."],
        ["R10\nProfitability metrics", "PASS",
         "ROE, ROA (average equity/assets), EBITDA margin, net margin. "
         "Currency translation and parent-profit conventions disclosed."],
        ["R11\nLeverage / liquidity", "PASS",
         "Net debt/EBITDA, D/E, current ratio, quick ratio (excludes inventory). "
         "4× EBITDA threshold declared as airline assumption (not industry standard)."],
        ["R12\nValuation ratios", "PASS",
         "P/E, P/B, EV/EBITDA computed from TRY prices and TRY financials (same basis, "
         "no FX conversion required)."],
        ["R13\nFundamental score", "PASS",
         "5-point scoring: growth>15%, profit growth>15%, ROE>20%, P/E≤median, leverage<4×. "
         "710 / 749 sessions complete; missingness explicit."],
        ["R14\nCombined trading strategy", "PASS",
         "60% technical + 40% fundamental; combined score ≥0.70 required. "
         "BUY/SELL/HOLD rules in strategy/rules.py; next-open execution."],
        ["R15\nNo look-ahead backtest", "PASS",
         "Release-date exclusion, pivot right-window confirmation, next-open fills. "
         "Source correction followed USD-result inspection (disclosed, not pristine blind)."],
        ["R16\nBenchmarks / performance metrics", "PASS",
         "4-way: combined, technical-only, buy-and-hold, BIST100. "
         "Sharpe, max drawdown, win rate, exposure, annual/holdout splits."],
        ["R17\nReal MCP AI agent", "PASS",
         f"{F['tools']} MCP tools; fine-tuned bist-qwen via Ollama; scripts/local_agent.py, scripts/ask.py; "
         "5 pre-run scenario traces (outputs/presentation/); 5-stage harness A-E; full tool-call traces."],
        ["R18\nVisuals / explanation", "PASS",
         "HTML/MD/PDF report, technical/scores/equity-drawdown charts, "
         "results tables; conclusions acknowledge underperformance; no invented numbers."],
        ["R19\nSubmission categories", "AMBER — now complete",
         "All 8 categories implemented. Presentation slides (this deliverable) now created. "
         "See deliverable inventory in ACCEPTANCE.md."],
    ]

    cw = [TW * 0.18, TW * 0.14, TW * 0.68]
    tdata = []
    for i, row in enumerate(req_rows):
        if i == 0:
            tdata.append(row)
        else:
            rid, stat, ev = row
            tdata.append([
                P(rid.replace("\n", "<br/>"), S["cell_bold"]),
                _status_cell(stat, S["cell"]),
                P(ev, S["cell"]),
            ])
    story.append(Table(tdata, colWidths=cw, style=_table_style(len(tdata) - 1)))
    story.append(PageBreak())

    # ── Section 3 — instructorQA.txt Additional Requirements ─────────────────
    story += [
        P("3. Additional Requirements from Project Announcement (instructorQA.txt)", S["h1"]),
        HRFlowable(width=TW, thickness=1, color=_NAVY_HEX, spaceAfter=8),
        P(
            'The project announcement PDF ("What does develop your own LLM mean?") added '
            "requirements beyond the base PDF. All are met.",
            S["body"],
        ),
        Spacer(1, 0.3 * cm),
    ]

    qa_req = [
        [P("Requirement", S["cell_hdr"]), P("Status", S["cell_hdr"]), P("Evidence", S["cell_hdr"])],
        ["Fine-tune an open-source LLM (1-8B) with LoRA/QLoRA",
         "DONE",
         "Qwen 2.5 3B + LoRA rank 16 / alpha 32. QLoRA 4-bit via Unsloth on Colab T4. "
         f"training/train_unsloth.py; adapter training/adapter/adapter_model.safetensors "
         f"(SHA-256 {F['adapter_sha'][:12]}…); merged GGUF {F['gguf_gb']} GB."],
        ["LLM interprets questions and calls correct MCP tools",
         "DONE",
         f"scripts/local_agent.py wires {F['tools']} MCP tools; the presentation path uses the "
         "fine-tune's own <tool_call> format. In all five scenario traces the model chose the "
         "intended tool on its own (questions never name a tool)."],
        ["LLM writes explanations from tool outputs only — no invented numbers",
         "DONE",
         "Grounding audit (src/bist_analytics/harness/grounding.py) traces every answer figure "
         "to a tool output; all five scenario traces pass. Label thresholds come from the tools "
         "(label_rule). Training answers were rejected if any figure was ungrounded."],
        ["LLM conclusion from 8-label action space only",
         "DONE",
         "schemas.py EDUCATIONAL_LABELS tuple (frozen). SYSTEM_PROMPT lists all 8. "
         "Evaluator flags any unlisted CAPS_TOKEN. Labels emitted by fine-tune: "
         "INVESTIGATE, HOLD, TECHNICAL_REVERSAL_CANDIDATE, FUNDAMENTAL_IMPROVEMENT_CANDIDATE, "
         "POTENTIAL_CATCH_UP_CANDIDATE, ANALYSIS_UNSAFE."],
        ["4 mandatory scenarios: sector lag, weekday, reversal, fundamentals",
         "DONE",
         "outputs/universe10/scenarios/ (Python studies: 92 laggard anchors, 1458 reversal events, "
         "19 fundamental releases) and the model's own pre-run traces for S1-S4 plus an "
         "ANALYSIS_UNSAFE case in outputs/presentation/traces/."],
        ["System runs fully locally — no cloud AI calls",
         "DONE",
         "Ollama on localhost:11434; MCP server is a local subprocess (stdin/stdout). "
         "Network disabled during demo per LOCAL_MODEL.md § offline verification."],
        ["Student builds the fine-tuning dataset",
         "DONE",
         f"training/dataset/build.py replays live MCP tool calls to generate {F['total_examples']} "
         f"examples (v3): sector {F['built'].get('sector_lag')}, weekday {F['built'].get('weekday')}, "
         f"reversal {F['built'].get('reversal')}, fundamental {F['built'].get('fundamental')}, "
         f"unsafe/unavailable {F['built'].get('analysis_unsafe')}; presentation settings held out."],
        ["Compare base vs fine-tuned model on §30 metrics",
         "DONE",
         "outputs/training/base_vs_finetuned.md: 8 metrics, base vs fine-tuned under two agent "
         "protocols, per-question labels, chart in outputs/training/figures/."],
    ]

    qa_data = []
    for i, row in enumerate(qa_req):
        if i == 0:
            qa_data.append(row)
        else:
            qa_data.append([
                P(row[0], S["cell"]),
                _status_cell(row[1], S["cell"]),
                P(row[2], S["cell"]),
            ])
    story.append(Table(qa_data, colWidths=[TW * 0.32, TW * 0.10, TW * 0.58],
                        style=_table_style(len(qa_data) - 1)))
    story.append(PageBreak())

    # ── Section 4 — §30 Metrics ───────────────────────────────────────────────
    from reportlab.platypus import Image
    ev = F["eval"].get("protocols", {})
    story += [
        P("4. §30 Evaluation Metrics — Base vs Fine-Tuned", S["h1"]),
        HRFlowable(width=TW, thickness=1, color=_NAVY_HEX, spaceAfter=8),
        P(
            "Measured by training/eval/run_baseline.py on the 20-question eval set. Base = "
            f"{F['eval'].get('models', {}).get('base', 'base')} (Qwen 2.5 3B Instruct with the same "
            "16k context and sampling); fine-tuned = bist-qwen. Temperature 0, seed 17. "
            "Presentation protocol: the settings of ask.py and the scenario traces (no tool "
            "schemas, training-format tool calls, RAG). Original protocol: Ollama sends the tool "
            "schemas (the earlier evaluation's settings).",
            S["body"],
        ),
        Spacer(1, 0.3 * cm),
    ]
    hdr = [P(x, S["cell_hdr"]) for x in ("Metric", "Base<br/>(pres.)", "Fine-tuned<br/>(pres.)",
                                         "Verdict", "Base<br/>(orig.)", "Fine-tuned<br/>(orig.)", "Verdict")]
    m_data = [hdr]
    for key in ("invalid_tool_call_rate", "missing_required_tool_rate", "label_mismatch_rate",
                "advice_leak_rate", "unknown_label_emitted_rate", "ungrounded_answer_rate",
                "max_turns_exceeded_rate", "reproducibility_rate"):
        row = [P(key, S["cell_bold"])]
        for proto in ("presentation", "original"):
            m = ev.get(proto, {}).get("metrics", {}).get(key)
            row += ([P(_pct(m["base"]), S["cell"]), P(_pct(m["finetuned"]), S["cell"]), P(m["verdict"], S["cell_bold"])]
                    if m else [P("n/a", S["cell"])] * 3)
        m_data.append(row)
    story.append(Table(m_data, colWidths=[TW * 0.31] + [TW * 0.115] * 6,
                       style=_table_style(len(m_data) - 1)))
    tallies = " ".join(
        f"{proto.capitalize()} protocol: {t['improved']} improved, {t['tie']} tied, {t['regressed']} regressed."
        for proto in ("presentation", "original") if (t := ev.get(proto, {}).get("tally")))
    story += [Spacer(1, 0.3 * cm), P(tallies + " " + EVAL_READING, S["note"])]
    chart = ROOT / "outputs" / "training" / "figures" / "base_vs_finetuned.png"
    if chart.exists():
        story += [Spacer(1, 0.3 * cm), Image(str(chart), width=TW, height=TW * 5.4 / 12.8)]
    story.append(PageBreak())

    # ── Section 5 — 5-Stage Harness ───────────────────────────────────────────
    story += [
        P("5. Five-Stage Harness Progression (bist-qwen)", S["h1"]),
        HRFlowable(width=TW, thickness=1, color=_NAVY_HEX, spaceAfter=8),
        P(
            "The harness re-runs a single THYAO.IS analysis question through 5 architectures, "
            "each adding one layer. This isolates the contribution of tools, state, evidence "
            "gate, and human review — independent of which LLM is used.",
            S["body"],
        ),
        Spacer(1, 0.3 * cm),
    ]

    stages = F["harness"].get("stages", [])

    def _hv(v):
        return ("Yes" if v else "No") if isinstance(v, bool) else f"{(v or 0):.1f}"

    def _ht(vals):
        nums = [float(v or 0) for v in vals]
        if len(set(nums)) == 1 and nums[0] > 0:
            return f"YES ({len(nums)}/{len(nums)})"
        if len(set(nums)) == 1:
            return "Flat"
        if all(a <= b for a, b in zip(nums, nums[1:])):
            return "YES"
        return f"Partial ({sum(1 for x in nums if x > 0)}/{len(nums)})"

    harness_data = [
        [P("Metric (axis)", S["cell_hdr"]), P("A: raw_llm", S["cell_hdr"]),
         P("B: llm_tools", S["cell_hdr"]), P("C: stateful", S["cell_hdr"]),
         P("D: evidence_gate", S["cell_hdr"]), P("E: memory_review", S["cell_hdr"]),
         P("Monotonic?", S["cell_hdr"])],
    ] + [[f"{label} ↑"] + [_hv(st.get(key)) for st in stages] + [_ht([st.get(key) for st in stages])]
         for key, label in (("evidence_coverage", "evidence_coverage"),
                            ("workflow_completion", "workflow_completion"),
                            ("structured_reproducibility", "structured_repro"),
                            ("constraint_compliance", "constraint_compliance"),
                            ("temporal_validity", "temporal_validity"),
                            ("numeric_exactness", "numeric_exactness"))]

    h_data = []
    for i, row in enumerate(harness_data):
        if i == 0:
            h_data.append(row)
        else:
            metric = row[0]
            vals = row[1:-1]
            mono = row[-1]
            mono_col = "#2e8b57" if "YES" in mono else ("#c97000" if "Partial" in mono else "#888888")
            from reportlab.lib import colors as rc
            from reportlab.lib.styles import ParagraphStyle
            mono_s = ParagraphStyle(
                f"mono_{i}", parent=S["cell"],
                textColor=rc.HexColor(mono_col), fontName="Helvetica-Bold",
            )
            h_data.append([P(metric, S["cell_bold"])] +
                           [P(v, S["cell"]) for v in vals] +
                           [P(mono, mono_s)])

    cw_h = [TW * 0.20] + [TW * 0.11] * 5 + [TW * 0.14]
    story.append(Table(h_data, colWidths=cw_h, style=_table_style(len(h_data) - 1)))
    story += [
        Spacer(1, 0.3 * cm),
        P(
            HARNESS_READING,
            S["note"],
        ),
        PageBreak(),
    ]

    # ── Section 6 — Training Summary ──────────────────────────────────────────
    story += [
        P("6. Fine-Tuning Configuration (from docs/MODEL_CARD.md)", S["h1"]),
        HRFlowable(width=TW, thickness=1, color=_NAVY_HEX, spaceAfter=8),
    ]

    hy = F["hyper"]
    train_cfg = [
        [P("Parameter", S["cell_hdr"]), P("Value", S["cell_hdr"])],
        ["Base model", f"{F['base'].get('upstream')} @ {str(F['base'].get('upstream_revision'))[:12]} "
                       f"(training checkpoint {F['base'].get('training_checkpoint')}); "
                       f"{F['base'].get('license')}"],
        ["Fallback reason", "Colab T4 has 14.56 GB VRAM; 7B QLoRA is marginal after logit upcast. "
                            "3B uses identical chat template and tokenizer."],
        ["LoRA rank / alpha", f"{hy.get('lora_rank')} / {hy.get('lora_alpha')}"],
        ["LoRA dropout",  f"{hy.get('lora_dropout')}"],
        ["LoRA targets",  "q, k, v, o projections + MLP projections"],
        ["Quantisation",  "QLoRA 4-bit nf4 (Unsloth)"],
        ["Epochs",        f"{hy.get('epochs')}"],
        ["Batch size",    f"{hy.get('per_device_batch')} (gradient accumulation {hy.get('grad_accum')} → "
                          f"effective batch {hy.get('effective_batch')})"],
        ["Learning rate", f"{hy.get('learning_rate')} {hy.get('lr_scheduler')} schedule"],
        ["Max sequence",  f"{hy.get('max_seq_length')} tokens"],
        ["Training time", f"{F['train_min']} min on {F['env'].get('gpu')} "
                          f"(peak {F['env'].get('peak_gpu_memory_gb')} GB)"],
        ["Loss",          f"train {F['train_loss']:.4f}, eval {F['eval_loss']:.4f} at step "
                          f"{F['steps']}/{F['steps']}"],
        ["Loss masking",  "train_on_responses_only (SFT; no RLHF)"],
        ["Adapter",       f"training/adapter/adapter_model.safetensors, SHA-256 {F['adapter_sha']}"],
        ["Export",        "Merged GGUF (q4_k_m) from the same run; "
                          f"{F['gguf_gb']} GB file at training/bist_lora.gguf"],
        ["Deployment",    "Ollama tag bist-qwen via training/Modelfile.finetuned (num_ctx 16384)"],
    ]

    t_data = [[train_cfg[0][0], train_cfg[0][1]]]
    for k, v in train_cfg[1:]:
        t_data.append([P(k, S["cell_bold"]), P(v, S["cell"])])
    story.append(Table(t_data, colWidths=[TW * 0.28, TW * 0.72],
                        style=_table_style(len(t_data) - 1)))

    story += [Spacer(1, 0.6 * cm), P("Dataset Distribution", S["h2"])]

    dist_data = [
        [P("Scenario", S["cell_hdr"]), P("Examples", S["cell_hdr"]), P("Description", S["cell_hdr"])],
        ["S1 — Sector laggards", str(F["built"].get("sector_lag")), "rank_sector_relative_strength; answers copy sector_summary"],
        ["S2 — Weekday patterns", str(F["built"].get("weekday")), "test_weekday_pattern; answers copy the summary block"],
        ["S3 — Reversal events", str(F["built"].get("reversal")), "detect_reversal_events; answers copy best_family"],
        ["S4 — Fundamental reaction", str(F["built"].get("fundamental")), "calculate_fundamental_change incl. publication reaction"],
        ["ANALYSIS_UNSAFE / unavailable", str(F["built"].get("analysis_unsafe")), "future dates, unknown tickers, missing fundamentals"],
        ["Total", str(F["total_examples"]), "80/20 split, stratified; presentation settings held out"],
    ]
    d_data = [dist_data[0]]
    for row in dist_data[1:]:
        d_data.append([P(row[0], S["cell_bold"]), P(row[1], S["cell"]), P(row[2], S["cell"])])
    story.append(Table(d_data, colWidths=[TW * 0.28, TW * 0.10, TW * 0.62],
                        style=_table_style(len(d_data) - 1)))

    story += [Spacer(1, 0.6 * cm), P("Running the Model Locally", S["h2"])]
    run_steps = [
        [P("Step", S["cell_hdr"]), P("Command / detail", S["cell_hdr"])],
        ["1. Install Ollama", "Windows/macOS/Linux installer from ollama.com; it runs as a local "
                              "service on 127.0.0.1:11434 (bundles llama.cpp)."],
        ["2. Register the model", "ollama create bist-qwen -f training/Modelfile.finetuned "
                                  "(loads the merged q4_k_m GGUF at training/bist_lora.gguf)."],
        ["3. Pre-run scenarios", ".\\.venv\\Scripts\\python.exe scripts\\run_presentation_scenarios.py "
                                 "(writes outputs/presentation/traces/S1-S5)"],
        ["4. Ask a question", ".\\.venv\\Scripts\\python.exe scripts\\ask.py \"&lt;question&gt;\" "
                              "(same model, prompts and settings as the scenarios)"],
        ["5. Verify", ".\\.venv\\Scripts\\python.exe scripts\\verify_submission.py "
                      "(hashes, adapter vs training record, 5 grounded traces)"],
        ["How it works", "scripts/local_agent.py starts the MCP server as a stdio child process, "
                         "adds knowledge-base context, sends the conversation to Ollama's "
                         "/v1/chat/completions endpoint and runs the tool calls the model writes "
                         "until it answers. Each run writes an execution trace with a grounding audit."],
        ["Offline / GPU", "The only connection is localhost:11434. With OLLAMA_FLASH_ATTENTION=1 and "
                          "OLLAMA_KV_CACHE_TYPE=q8_0 the 3B Q4 model runs fully on a 4 GB GPU "
                          "(about 25 s per question); CPU-only also works, more slowly."],
    ]
    r_data = [run_steps[0]]
    for k, v in run_steps[1:]:
        r_data.append([P(k, S["cell_bold"]), P(v, S["cell"])])
    story.append(Table(r_data, colWidths=[TW * 0.22, TW * 0.78],
                        style=_table_style(len(r_data) - 1)))

    story += [
        Spacer(1, 0.6 * cm),
        P("Known Limitations", S["h2"]),
        *[P(f"{i}. {text}", S["body"]) for i, text in enumerate(LIMITATIONS_TEXT, start=1)],
        PageBreak(),
    ]

    # ── Section 7 — Scenario Summary ──────────────────────────────────────────
    story += [
        P("7. Scenario Report Summary (outputs/universe10/scenarios/)", S["h1"]),
        HRFlowable(width=TW, thickness=1, color=_NAVY_HEX, spaceAfter=8),
    ]

    scenario_data = [
        [P("Scenario", S["cell_hdr"]), P("Output file", S["cell_hdr"]),
         P("Key statistics", S["cell_hdr"])],
        ["S1 — Sector Laggards (catch-up)", "s1_sector_laggard.md / .csv",
         "92 weekly anchors across 5 sectors. 20-day hit rate vs sector peers: "
         "steel 60.9%, banking 54.3%, airlines 44.6%."],
        ["S2 — Weekday Patterns", "s2_weekday.md / .csv",
         "50 weekday observations across 10 tickers. "
         "Pattern significance tested via test_weekday_pattern MCP tool."],
        ["S3 — Reversal Events", "s3_reversals.md / .csv",
         "1458 reversal events detected. 5-day bounce rate: BB lower-touch 58.7%, "
         "RSI oversold recovery 59.1%. SUPERTREND_FLIP_UP also captured."],
        ["S4 — Fundamental Reaction", "s4_fundamental_reaction.md / .csv",
         "THYAO.IS only: 7 release dates (19 panel rows). Mean 5-day return "
         "vs BIST100 after a release: -1.29%."],
    ]

    s_data = [scenario_data[0]]
    for row in scenario_data[1:]:
        s_data.append([P(row[0], S["cell_bold"]), P(row[1], S["cell"]), P(row[2], S["cell"])])
    story.append(Table(s_data, colWidths=[TW * 0.22, TW * 0.20, TW * 0.58],
                        style=_table_style(len(s_data) - 1)))

    story += [
        Spacer(1, 0.4 * cm),
        P(
            "All four scenario reports were generated by scripts/build_scenarios.py "
            "--config config/universe10.yaml and are committed to the repository. "
            "They constitute direct evidence for the four mandatory scenarios stated in the "
            "project announcement.",
            S["body"],
        ),
    ]

    doc.build(story)


# ─────────────────────────────────────────────────────────────────────────────
#  DELIVERABLE 2 — Presentation Slides (HTML)
# ─────────────────────────────────────────────────────────────────────────────

def build_presentation_slides(out: Path) -> None:  # noqa: PLR0912, PLR0915

    css = """\
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
       background: #111; color: #fff; }
.slide {
  width: 100vw; min-height: 100vh;
  display: flex; flex-direction: column; justify-content: center;
  padding: 4rem 7rem;
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 60%, #0f3460 100%);
  page-break-after: always; break-after: page;
  position: relative;
}
.slide-num {
  position: absolute; top: 1.4rem; right: 2rem;
  font-size: 0.75rem; color: #556; letter-spacing: 2px;
}
.tag {
  display: inline-block; background: #e94560; color: #fff;
  font-size: 0.7rem; font-weight: 700; padding: 2px 10px;
  border-radius: 2px; letter-spacing: 1px; margin-bottom: 1rem;
  text-transform: uppercase;
}
h1 { font-size: 2.4rem; color: #e94560; margin-bottom: 1.2rem; line-height: 1.2; }
h2 { font-size: 1.5rem; color: #e94560; margin-bottom: 0.8rem; }
.subtitle { font-size: 1.1rem; color: #aab; margin-bottom: 0.4rem; }
p  { font-size: 0.98rem; line-height: 1.75; color: #ccd; margin-bottom: 0.6rem; }
ul { margin-left: 1.4rem; }
ul li { font-size: 0.95rem; line-height: 1.7; color: #ccd; margin-bottom: 0.3rem; }
ul li strong { color: #fff; }
code, .mono {
  font-family: 'Consolas', 'Cascadia Code', monospace;
  background: rgba(255,255,255,0.08); padding: 2px 6px;
  border-radius: 3px; font-size: 0.85rem; color: #e0e0ff;
}
.cols { display: grid; grid-template-columns: 1fr 1fr; gap: 2.5rem; margin-top: 0.5rem; }
.cols3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 1.5rem; margin-top: 0.5rem; }
.card {
  background: rgba(255,255,255,0.06); border-radius: 8px;
  padding: 1.2rem 1.4rem; border-left: 3px solid #e94560;
}
.card h3 { font-size: 1rem; color: #e94560; margin-bottom: 0.5rem; }
.card p  { font-size: 0.85rem; color: #bbc; margin-bottom: 0.3rem; }
table { width: 100%; border-collapse: collapse; margin-top: 0.6rem; font-size: 0.82rem; }
th { background: #e94560; color: #fff; padding: 6px 10px; text-align: left; }
td { padding: 5px 10px; border-bottom: 1px solid rgba(255,255,255,0.08);
     color: #ccd; vertical-align: top; }
tr:nth-child(even) td { background: rgba(255,255,255,0.03); }
.pass  { color: #4caf50; font-weight: 700; }
.tied  { color: #90caf9; font-weight: 700; }
.note  { color: #f9a825; font-weight: 700; }
.arrow { color: #e94560; font-size: 1.3rem; }
.big-stat { font-size: 2.4rem; font-weight: 700; color: #e94560; }
.stat-label { font-size: 0.75rem; color: #889; text-transform: uppercase;
              letter-spacing: 1px; margin-top: 0.1rem; }
hr { border: none; border-top: 1px solid rgba(255,255,255,0.12);
     margin: 1rem 0; }
@media print {
  @page { size: landscape; margin: 0; }
  .slide { width: 100vw; height: 100vh; min-height: 100vh; overflow: hidden; }
}
"""

    slides = []

    # ── Slide 1 — Title ───────────────────────────────────────────────────────
    slides.append(f"""\
<div class="tag">CSE481 · Engineering Economics</div>
<h1>BIST Financial Analysis Agent</h1>
<p class="subtitle">A locally-hosted fine-tuned LLM for reproducible BIST equity analysis</p>
<hr>
<div class="cols" style="margin-top:1.5rem">
  <div>
    <p><strong>Student:</strong> Yavuz Selim</p>
    <p><strong>Course:</strong> CSE481 Engineering Economics, 2026</p>
    <p><strong>Model:</strong> <code>bist-qwen</code> (Qwen 2.5 3B + LoRA via Ollama)</p>
  </div>
  <div>
    <p><strong>{F['tickers']}</strong> tickers · <strong>{F['sectors']}</strong> sectors (agent universe)</p>
    <p><strong>{F['tools']}</strong> MCP tools · <strong>{F['total_examples']}</strong> training examples</p>
    <p><strong>5</strong> pre-run scenario traces · every figure audited</p>
  </div>
</div>""")

    # ── Slide 2 — Problem Statement ───────────────────────────────────────────
    slides.append("""\
<div class="tag">Problem</div>
<h1>Problem Statement</h1>
<p>Can a locally-hosted fine-tuned LLM give reproducible, evidence-grounded<br>
BIST equity analysis — without inventing numbers or giving investment advice?</p>
<hr>
<div class="cols">
  <div class="card">
    <h3>Two Hard Constraints</h3>
    <p>🔢 <strong>Never invent numbers</strong> — every numeric claim must come from a tool output</p>
    <p>⚠️ <strong>No investment advice</strong> — only 8 educational labels allowed</p>
  </div>
  <div class="card">
    <h3>Why Local?</h3>
    <p>✓ Fully verifiable — offline, no cloud dependency</p>
    <p>✓ Reproducible — same model, seed 17, temperature 0, same answers</p>
    <p>✓ Student-controlled — no API keys, no costs</p>
  </div>
</div>
<div style="margin-top:1.4rem">
  <p><strong>8 Educational Labels (the only allowed conclusions):</strong></p>
  <p><code>HOLD</code> &nbsp; <code>WATCH</code> &nbsp; <code>INVESTIGATE</code> &nbsp;
     <code>POTENTIAL_CATCH_UP_CANDIDATE</code> &nbsp; <code>TECHNICAL_REVERSAL_CANDIDATE</code></p>
  <p><code>FUNDAMENTAL_IMPROVEMENT_CANDIDATE</code> &nbsp;
     <code>REJECT_SIGNAL</code> &nbsp; <code>ANALYSIS_UNSAFE</code></p>
</div>""")

    # ── Slide 3 — System Architecture ─────────────────────────────────────────
    slides.append(f"""\
<div class="tag">Architecture</div>
<h1>System Architecture</h1>
<div class="cols3" style="margin-top:1rem">
  <div class="card">
    <h3>Layer 1 — Data</h3>
    <p>Yahoo Finance OHLCV ({F['tickers']} tickers)</p>
    <p>Fintables TMS29 financials</p>
    <p>KAP context events</p>
    <p>RAG knowledge base ({F['kb_docs']} docs)</p>
  </div>
  <div class="card">
    <h3>Layer 2 — MCP Server</h3>
    <p>{F['tools']} read-only tools (incl. BM25 search)</p>
    <p>stdio transport (subprocess)</p>
    <p>Comparisons precomputed in Python</p>
    <p>All tools return JSON evidence</p>
  </div>
  <div class="card">
    <h3>Layer 3 — LLM Agent</h3>
    <p><code>bist-qwen</code> via Ollama, on the laptop GPU</p>
    <p>Tool calls in its training format</p>
    <p>Grounding audit on every answer</p>
    <p>8-label action space</p>
  </div>
</div>
<hr>
<p style="margin-top:0.8rem"><strong>5-Stage Harness A→E</strong> (adds one layer per stage):</p>
<table style="margin-top:0.4rem">
  <tr><th>A: raw_llm</th><th>B: llm_tools</th><th>C: stateful</th>
      <th>D: evidence_gate</th><th>E: memory_review</th></tr>
  <tr><td>Base LLM only<br>No tools</td>
      <td>+ {F['tools']} MCP tools<br>Tool-calling enabled</td>
      <td>+ State context<br>as_of, financial period</td>
      <td>+ Quality gate<br>ANALYSIS_UNSAFE blocking</td>
      <td>+ Memory layer<br>Human review sign-off</td></tr>
</table>""")

    # ── Slide 4 — Data Architecture ───────────────────────────────────────────
    sector_list = ", ".join(s.capitalize() for s in F["sector_names"])
    slides.append(f"""\
<div class="tag">Data</div>
<h1>Data Architecture — 3 Tiers</h1>
<div class="cols3" style="margin-top:1rem">
  <div class="card">
    <h3>Tier 1: Market Data</h3>
    <p><strong>Source:</strong> Yahoo Finance (cached)</p>
    <p><strong>Tickers:</strong> {F['tickers']} BIST stocks + XU100.IS</p>
    <p><strong>Sectors:</strong> {sector_list}</p>
    <p><strong>OHLCV:</strong> daily, 2021-01-04 to 2026-10-30</p>
  </div>
  <div class="card">
    <h3>Tier 2: Fundamental Data</h3>
    <p><strong>Source:</strong> Fintables TMS29</p>
    <p><strong>Scope:</strong> THYAO, 2025–2026 (post-inflation-adjustment)</p>
    <p><strong>Observations:</strong> 238 verified</p>
    <p><strong>Other tickers:</strong> tools return <code>available: false</code></p>
  </div>
  <div class="card">
    <h3>Tier 3: Context &amp; Knowledge</h3>
    <p><strong>KAP:</strong> 13 THYAO corporate events</p>
    <p><strong>RAG:</strong> {F['kb_docs']} documents with source metadata</p>
    <p><strong>FX:</strong> USD/TRY (Yahoo TRY=X), cached</p>
    <p><strong>TCMB / TÜİK, speech:</strong> tools built; no series cached</p>
  </div>
</div>
<hr>
<p><strong>Key design rule:</strong> All analysis runs from <em>cached</em> data.
No network calls during backtest or reporting. Knowledge-base hits are filtered to documents
published on or before the question's date (point-in-time).</p>""")

    # ── Slide 5 — MCP Tools ───────────────────────────────────────────────────
    slides.append(f"""\
<div class="tag">Tools</div>
<h1>{F['tools']} MCP Tools — The Agent's Calculator</h1>
<div class="cols" style="margin-top:0.8rem">
  <div>
    <table>
      <tr><th colspan="2">Market &amp; Scoring</th></tr>
      <tr><td><code>get_stock_history</code></td><td>OHLCV for any ticker</td></tr>
      <tr><td><code>get_index_history</code></td><td>XU100 benchmark</td></tr>
      <tr><td><code>calculate_indicators</code></td><td>SMA/EMA/RSI/MACD/BB/Supertrend</td></tr>
      <tr><td><code>find_support_resistance</code></td><td>Pivot clustering</td></tr>
      <tr><td><code>get_fundamental_metrics</code></td><td>Revenue, ROE, leverage…</td></tr>
      <tr><td><code>calculate_scores</code></td><td>Technical + fundamental score</td></tr>
      <tr><td><code>generate_signal</code></td><td>BUY / SELL / HOLD signal</td></tr>
      <tr><td><code>run_backtest</code></td><td>Strategy backtest + metrics</td></tr>
      <tr><td><code>generate_report</code></td><td>HTML / Markdown output</td></tr>
      <tr><td><code>search_knowledge_base</code></td><td>BM25 RAG, point-in-time</td></tr>
    </table>
  </div>
  <div>
    <table>
      <tr><th colspan="2">Scenario &amp; Quality</th></tr>
      <tr><td><code>rank_sector_relative_strength</code></td><td>Laggard/leader per sector + rule label</td></tr>
      <tr><td><code>test_weekday_pattern</code></td><td>Highest/lowest weekday, p-values</td></tr>
      <tr><td><code>detect_reversal_events</code></td><td>Events + best family by 5-day return</td></tr>
      <tr><td><code>calculate_fundamental_change</code></td><td>QoQ change + publication reaction</td></tr>
      <tr><td><code>get_macro_context</code></td><td>TCMB / TÜİK reader (no cache shipped)</td></tr>
      <tr><td><code>get_news_events</code></td><td>KAP news events</td></tr>
      <tr><td><code>get_speech_features</code></td><td>Speech text features</td></tr>
      <tr><td><code>check_data_quality</code></td><td>Gate: future date / unknown ticker</td></tr>
      <tr><td><code>build_evidence_bundle</code></td><td>EvidenceBundle with IDs</td></tr>
      <tr><td><code>get_context_events</code> / <code>project_status</code></td><td>Context &amp; status</td></tr>
    </table>
  </div>
</div>
<p style="margin-top:0.6rem; font-size:0.82rem; color:#aab">Each scenario tool returns its
comparison and the label its rule gives (<code>label_by_rule</code>), so the model copies
tool values instead of doing arithmetic.</p>""")

    # ── Slide 6 — Fine-Tuning Pipeline ────────────────────────────────────────
    hy, b = F["hyper"], F["built"]
    slides.append(f"""\
<div class="tag">Fine-Tuning</div>
<h1>Fine-Tuning Pipeline</h1>
<div style="display:flex; align-items:center; gap:1rem; margin-top:1rem; font-size:0.9rem">
  <div class="card" style="flex:1; text-align:center">
    <h3>Base Model</h3>
    <p>Qwen 2.5 3B Instruct</p>
    <p>(Qwen Research License)</p>
  </div>
  <div class="arrow">→</div>
  <div class="card" style="flex:1; text-align:center">
    <h3>Dataset</h3>
    <p>{F['total_examples']} traces from live MCP calls</p>
    <p>every answer figure audited</p>
  </div>
  <div class="arrow">→</div>
  <div class="card" style="flex:1; text-align:center">
    <h3>QLoRA Training</h3>
    <p>Colab {F['env'].get('gpu', 'T4')}</p>
    <p>{F['train_min']} min · {hy.get('epochs')} epochs</p>
    <p>eval_loss = {F['eval_loss']:.4f}</p>
  </div>
  <div class="arrow">→</div>
  <div class="card" style="flex:1; text-align:center">
    <h3>Export</h3>
    <p>Merged GGUF (q4_k_m)</p>
    <p>{F['gguf_gb']} GB file</p>
  </div>
  <div class="arrow">→</div>
  <div class="card" style="flex:1; text-align:center">
    <h3>Deploy</h3>
    <p>Ollama tag <code>bist-qwen</code></p>
    <p>100% on a 4 GB laptop GPU</p>
  </div>
</div>
<hr>
<div class="cols">
  <div>
    <p><strong>LoRA:</strong> rank {hy.get('lora_rank')} · alpha {hy.get('lora_alpha')} · dropout {hy.get('lora_dropout')} on q/k/v/o + MLP</p>
    <p><strong>Training:</strong> max_len {hy.get('max_seq_length')} · effective batch {hy.get('effective_batch')} · lr {hy.get('learning_rate')} cosine · seed {hy.get('seed')}</p>
    <p><strong>Adapter:</strong> safetensors, SHA-256 <code>{F['adapter_sha'][:16]}…</code></p>
  </div>
  <div>
    <p><strong>Dataset (v3, {F['total_examples']} total):</strong> sector {b.get('sector_lag')} · weekday {b.get('weekday')} ·
       reversal {b.get('reversal')} · fundamental {b.get('fundamental')} · unsafe/unavailable {b.get('analysis_unsafe')}</p>
    <p><strong>Split:</strong> 80/20 train/eval · {round((F['natural_share'] or 0) * 100)}% natural-language questions (EN + TR)</p>
    <p><strong>Held out:</strong> the five presentation scenarios' exact settings</p>
  </div>
</div>""")

    # ── Slide 7 — 4 Scenarios ─────────────────────────────────────────────────
    slides.append("""\
<div class="tag">Scenarios</div>
<h1>4 Mandatory Scenario Reports</h1>
<table style="margin-top:1rem">
  <tr><th>Scenario</th><th>MCP Tool</th><th>Universe (10 tickers)</th><th>Key Finding</th></tr>
  <tr>
    <td><strong>S1 — Sector Laggards</strong><br><em>Catch-up analysis</em></td>
    <td><code>rank_sector_relative_strength</code></td>
    <td>5 sectors, all 10 tickers</td>
    <td>92 weekly anchors. Laggard beat its sector peers over 20 days: steel 60.9%, banking 54.3%, airlines 44.6%.</td>
  </tr>
  <tr>
    <td><strong>S2 — Weekday Patterns</strong><br><em>Day-of-week bias</em></td>
    <td><code>test_weekday_pattern</code></td>
    <td>All 10 tickers</td>
    <td>50 observations. Pattern significance varies by ticker; no universal weekday edge found.</td>
  </tr>
  <tr>
    <td><strong>S3 — Reversal Events</strong><br><em>Technical bounce signals</em></td>
    <td><code>detect_reversal_events</code></td>
    <td>All 10 tickers</td>
    <td>1,458 events detected. 5-day bounce rate: BB lower-touch 58.7% (230 events), RSI oversold recovery 59.1% (44 events).</td>
  </tr>
  <tr>
    <td><strong>S4 — Fundamental Reaction</strong><br><em>Post-earnings price move</em></td>
    <td><code>calculate_fundamental_change</code></td>
    <td>THYAO.IS only</td>
    <td>7 THYAO release dates (19 panel rows). Mean 5-day return vs BIST100 after a release: −1.29%.</td>
  </tr>
</table>
<p style="margin-top:0.8rem; font-size:0.82rem; color:#889">
  Python studies over the 10-ticker sample (no LLM involved): outputs/universe10/scenarios/ —
  scripts/build_scenarios.py --config config/universe10.yaml
</p>""")

    # ── Slide 8 — §30 Metrics ─────────────────────────────────────────────────
    ev = F["eval"].get("protocols", {})
    names = {"invalid_tool_call_rate": "invalid tool call", "missing_required_tool_rate": "missing required tool",
             "label_mismatch_rate": "label mismatch", "advice_leak_rate": "advice leak",
             "unknown_label_emitted_rate": "unknown label token", "ungrounded_answer_rate": "ungrounded figure",
             "max_turns_exceeded_rate": "no answer (turn limit)", "reproducibility_rate": "non-empty answer"}
    css_of = {"improved": "pass", "tie": "tied", "regressed": "note"}

    def _cells(proto: str, key: str) -> str:
        m = ev.get(proto, {}).get("metrics", {}).get(key)
        if not m:
            return "<td>n/a</td><td>n/a</td><td></td>"
        return (f"<td>{_pct(m['base'])}</td><td>{_pct(m['finetuned'])}</td>"
                f"<td class=\"{css_of[m['verdict']]}\">{m['verdict']}</td>")

    rows8 = "\n".join(
        f"  <tr><td>{label} {'↓' if key != 'reproducibility_rate' else '↑'}</td>"
        f"{_cells('presentation', key)}{_cells('original', key)}</tr>"
        for key, label in names.items())

    def _tally(proto: str) -> str:
        t = ev.get(proto, {}).get("tally")
        return (f"{t['improved']} improved · {t['tie']} tied · {t['regressed']} regressed" if t else "n/a")

    slides.append(f"""\
<div class="tag">Evaluation</div>
<h1>§30 Metrics — Base vs Fine-Tuned (20 questions)</h1>
<table style="margin-top:0.6rem">
  <tr><th rowspan="2">Metric (share of questions)</th>
      <th colspan="3">Presentation protocol (training format + RAG)</th>
      <th colspan="3">Original protocol (tool schemas)</th></tr>
  <tr><th>Base</th><th>Fine-tuned</th><th>Verdict</th><th>Base</th><th>Fine-tuned</th><th>Verdict</th></tr>
{rows8}
  <tr><td><strong>Tally (fine-tuned vs base)</strong></td><td colspan="3">{_tally('presentation')}</td>
      <td colspan="3">{_tally('original')}</td></tr>
</table>
<p style="margin-top:0.6rem; font-size:0.78rem; color:#aab">
  Base = <code>{F['eval'].get('models', {}).get('base', 'base')}</code> (Qwen 2.5 3B Instruct, same 16k context and sampling);
  fine-tuned = <code>bist-qwen</code>. Temperature 0, seed 17. The presentation protocol is what
  <code>ask.py</code> and the five scenario traces use. "Unknown label token" also counts quoted tool
  identifiers such as BB_LOWER_TOUCH. Full table: outputs/training/base_vs_finetuned.md
</p>""")

    # ── Slide 9 — Harness Progression ─────────────────────────────────────────
    stages = F["harness"].get("stages", [])
    axes9 = [("evidence_coverage", "evidence_coverage"), ("workflow_completion", "workflow_completion"),
             ("structured_reproducibility", "structured_repro"), ("constraint_compliance", "constraint_compliance"),
             ("temporal_validity", "temporal_validity"), ("numeric_exactness", "numeric_exactness")]

    def _fmt9(v) -> str:
        if isinstance(v, bool):
            return '<td class="pass">Yes</td>' if v else "<td>No</td>"
        return f'<td class="pass">{v:.1f}</td>' if v and v > 0 else f"<td>{(v or 0):.1f}</td>"

    def _trend(vals: list) -> str:
        nums = [float(v) for v in vals]
        if len(set(nums)) == 1 and nums[0] > 0:
            return f'<td class="pass">{len(nums)} / {len(nums)} pass</td>'
        if len(set(nums)) == 1:
            return '<td style="color:#888">Flat</td>'
        if all(a <= b for a, b in zip(nums, nums[1:])):
            return '<td class="pass">↑ Monotonic</td>'
        return f'<td class="note">{sum(1 for x in nums if x > 0)} / {len(nums)} pass</td>'

    rows9 = "\n".join(
        f"  <tr><td><code>{label}</code> ↑</td>{''.join(_fmt9(s.get(key)) for s in stages)}"
        f"{_trend([s.get(key) or 0 for s in stages])}</tr>" for key, label in axes9)
    base_stages = {s["stage"]: s for s in F["harness_base"].get("stages", [])}
    base_cov = " · ".join(f"{(base_stages.get(s['stage'], {}).get('evidence_coverage') or 0):.1f}" for s in stages)
    slides.append(f"""\
<div class="tag">Harness</div>
<h1>5-Stage Harness — Architecture Comparison</h1>
<table style="margin-top:1rem">
  <tr><th>Metric (bist-qwen)</th><th>A: raw_llm</th><th>B: llm_tools</th>
      <th>C: stateful</th><th>D: evid_gate</th><th>E: mem_review</th><th>Trend</th></tr>
{rows9}
</table>
<p style="margin-top:0.9rem; font-size:0.85rem; color:#ccd">
  Same THYAO question through each stage; only the architecture changes. Base model's
  evidence_coverage per stage, for comparison: {base_cov}.
  Files: outputs/harness/comparison.finetuned.json, comparison.base.json
</p>""")

    # ── Slide 10 — From v1 to v3 ─────────────────────────────────────────────
    slides.append("""\
<div class="tag">Engineering</div>
<h1>What Fixed the Model — v1 → v3</h1>
<table style="margin-top:0.8rem">
  <tr><th>Problem we observed</th><th>Root cause</th><th>Fix</th></tr>
  <tr><td>Endless tool loops (q06: 15 identical calls)</td><td>No "stop and answer" signal</td>
      <td>Dedup guard + per-turn token ceiling (1,536)</td></tr>
  <tr><td>Grounded numbers, wrong reasoning (wrong laggard of 4 banks, lost minus sign)</td>
      <td>A 3B model doing comparisons in its head</td>
      <td>Tools return the comparison + <code>label_by_rule</code>; answers copy it (dataset v3)</td></tr>
  <tr><td>Chained unrelated tools after the right one</td>
      <td>Trained without tool schemas, served with Ollama's 21-schema block</td>
      <td>Presentation path sends no schemas and parses <code>&lt;tool_call&gt;</code> text, as in training</td></tr>
  <tr><td>Answers ignored parts of long tool outputs</td><td>Trained on 3 KB tool text, served 12 KB</td>
      <td>One 4.5 KB cap for training and inference; summaries placed first</td></tr>
  <tr><td>Risk of testing on training data</td><td>Scenario settings could appear in the dataset</td>
      <td>The five presentation settings are held out of the 400 examples</td></tr>
</table>
<p style="margin-top:0.8rem; font-size:0.85rem; color:#ccd">
  Every answer still comes from the model, unedited; a grounding audit checks each figure against the tool outputs.
</p>""")

    # ── Slide 11 — Limitations ────────────────────────────────────────────────
    slides.append(LIMITATIONS_SLIDE)

    # ── Slide 12 — Pre-run scenarios + live question ─────────────────────────
    rows12 = "\n".join(
        f"  <tr><td><strong>{s['id']}</strong> {s['title']}</td><td><code>{', '.join(s['tools_called'])}</code></td>"
        f"<td><code>{s['label']}</code></td><td>{s['key']}</td>"
        f"<td>{'all' if s['all_grounded'] else 'NO'}</td><td>{(s['wall_time_s'] or 0):.0f} s</td></tr>"
        for s in F["scenarios"])
    slides.append(f"""\
<div class="tag">Demo</div>
<h1>Five Pre-Run Scenarios + Live Question</h1>
<table style="margin-top:0.6rem; font-size:0.76rem">
  <tr><th>Scenario</th><th>Tool the model chose</th><th>Label</th><th>Key figures (from the tool output)</th>
      <th>Grounded</th><th>Time</th></tr>
{rows12}
</table>
<div class="cols" style="margin-top:0.8rem">
  <div>
    <p style="font-size:0.85rem"><strong>Pre-run traces:</strong> <code>python scripts/run_presentation_scenarios.py</code></p>
    <p style="font-size:0.78rem; color:#aab">Each trace records model digest, prompts, tool calls with
      arguments and date ranges, tool outputs, final answer, timestamps, temperature 0 and seed 17.</p>
  </div>
  <div>
    <p style="font-size:0.85rem"><strong>Live question:</strong> <code>python scripts/ask.py "&lt;question&gt;"</code></p>
    <p style="font-size:0.78rem; color:#aab">Same model, prompts, settings and code path; prints each
      tool call, the answer, and the grounding audit. Only <code>127.0.0.1:11434</code> is used.</p>
  </div>
</div>""")

    # ── Assemble HTML ──────────────────────────────────────────────────────────
    slide_html = "\n\n".join(
        f'<section class="slide"><span class="slide-num">{i+1} / {len(slides)}</span>\n{body}\n</section>'
        for i, body in enumerate(slides)
    )

    html = f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>BIST Financial Analysis Agent — CSE481 Presentation</title>
<style>
{css}
</style>
</head>
<body>
{slide_html}
</body>
</html>
"""
    out.write_text(html, encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
#  DELIVERABLE 3 — Q&A Preparation PDF
# ─────────────────────────────────────────────────────────────────────────────

def build_qa_prep(out: Path) -> None:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        HRFlowable,
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
    )

    W, H = A4
    MARGIN = 2.2 * cm
    TW = W - 2 * MARGIN

    doc = SimpleDocTemplate(
        str(out), pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=MARGIN,
        title="CSE481 Presentation Q&A Preparation",
        author="Yavuz Selim",
    )
    S = _pdf_styles()
    P = Paragraph
    story = []

    # Cover
    story += [
        Spacer(1, 1.5 * cm),
        P("CSE481 Engineering Economics — Term Project", S["cover_sub"]),
        P("Anticipated Instructor Q&A — Preparation Document", S["cover_title"]),
        HRFlowable(width=TW, thickness=2, color=_NAVY_HEX, spaceAfter=16),
        P("Yavuz Selim · November 2026", S["cover_meta"]),
        Spacer(1, 0.5 * cm),
        P(
            "This document lists the most likely questions an instructor would ask "
            "during a live project presentation, together with accurate, concise answers. "
            "Organised into 6 topic groups. For each question, the answer is complete enough "
            "to respond confidently without reading from notes.",
            S["body"],
        ),
        PageBreak(),
    ]

    def qa(question: str, answer: str) -> list:
        return [P(question, S["q"]), P(answer, S["a"])]

    def section(title: str) -> list:
        return [
            Spacer(1, 0.4 * cm),
            P(title, S["h1"]),
            HRFlowable(width=TW, thickness=1, color=_BLUE_HEX, spaceAfter=6),
        ]

    # ── Group 1 — Model Choice ────────────────────────────────────────────────
    story += section("Group 1: Model Choice")

    story += qa(
        'Q1. Why Qwen 2.5 specifically? Why not Llama or Mistral?',
        "Qwen 2.5 Instruct has strong multi-language capability (Turkish ticker symbols and question phrasing) and a native tool-call format (<tool_call>{json}</tool_call>) that the fine-tune learned directly. The 3B variant fits a free Colab T4 for QLoRA and runs entirely on a 4 GB laptop GPU after quantisation, with the same tokenizer and chat template as the 7B. Tool outputs are capped at 4,500 characters on the presentation path, so a 16k context is enough.",
    )
    story += qa(
        "Q2. Why 3B parameters instead of your original 7B plan?",
        "A T4 GPU has 14.56 GB VRAM. 7B QLoRA with 4-bit weights + activations + logit upcast "
        "is marginal and caused OOM errors during training. The 3B Instruct uses the same chat "
        "template, the same tokeniser, and the same tool-calling format as the 7B — so all "
        "downstream code (harness, eval, Modelfile) works unchanged. For a 400-example "
        "domain-specific SFT task, 3B with LoRA is sufficient.",
    )
    story += qa(
        'Q3. Why QLoRA and not full fine-tuning?',
        f"Full fine-tuning of a 3B model needs roughly 12-24 GB of GPU memory. QLoRA trains only the LoRA adapter (about 1% of parameters) on a frozen 4-bit base. The submitted run took {F['train_min']} minutes on a Colab {F['env'].get('gpu')} (peak {F['env'].get('peak_gpu_memory_gb')} GB) for 3 epochs over {F['total_examples']} examples, ending at eval_loss {F['eval_loss']:.4f}. A loss that low mostly means the answer format is learned; correctness is judged on the scenario traces and the eval, not the loss.",
    )

    # ── Group 2 — Training Data ───────────────────────────────────────────────
    story += section("Group 2: Training Data")

    story += qa(
        "Q4. How did you build the training dataset?",
        "The script training/dataset/build.py replays live MCP tool calls against the committed "
        "Fintables and Yahoo cache. For each of the 4 mandatory scenarios (sector laggards, "
        "weekday patterns, reversal events, fundamental reaction) it generates question → "
        "tool-call sequence → tool output → evidence-based explanation tuples. Each example is "
        "verified: numeric fidelity is guaranteed to match the committed data vintages to 1e-6. "
        "An 80/20 train/eval split is applied, stratified by scenario.",
    )
    story += qa(
        'Q5. Why only 400 examples? Is that enough?',
        "Enough to teach the target behaviour for five question types: which tool to call, copy the tool's precomputed summary and label_by_rule, and stop. Every training answer was rejected if any of its figures did not appear in the tool output shown. It is not enough for general use: outside those five types the model is over-cautious (11 of 20 eval answers say ANALYSIS_UNSAFE where only 2 should), and it does not know tools it was not trained on.",
    )
    story += qa(
        "Q6. How do you guarantee the training data has no look-ahead bias?",
        "The training examples are generated from the same cached data that the backtest uses, "
        "which enforces release-date exclusion: financial metrics only enter after the Fintables "
        "publication date, pivot confirmations only after the right-window is complete, and "
        "all tool calls use an explicit as_of date parameter. The build.py script uses the same "
        "MCPStdioClient as the agent, so it goes through the same causal guards.",
    )

    # ── Group 3 — Architecture ────────────────────────────────────────────────
    story += section("Group 3: Architecture & Harness")

    story += qa(
        'Q7. What does each of the 5 harness stages add? Why not just go straight to stage E?',
        f"The harness isolates contributions on one fixed THYAO question: (A) raw_llm has no tools and scores 0 evidence_coverage; (B) llm_tools adds the {F['tools']} MCP tools and coverage jumps to 1.0; (C) stateful adds the as_of date and financial period; (D) evidence_quality_gate adds the ANALYSIS_UNSAFE blocking layer; (E) memory_review adds memory and human sign-off. The fine-tune keeps constraint_compliance in all 5 stages (base: 2 of 5). Going straight to E would hide which layer provides which benefit.",
    )
    story += qa(
        "Q8. Why so many MCP tools? Can't the LLM just calculate these itself?",
        f"The LLM explains; Python calculates. Letting a 3B model compute RSI, compare four banks or apply a threshold produced grounded numbers with wrong conclusions (v2: wrong laggard, a dropped minus sign). So the {F['tools']} tools are deterministic and cache-reproducible, and the scenario tools return the comparison and the label their rule gives; the model copies them. Re-running gives bit-identical tool outputs.",
    )
    story += qa(
        'Q9. What went wrong with earlier versions of the model, and how did you fix it?',
        "v1 looped on tool calls (q06: 15 identical calls); an inference-time dedup guard and a 1,536-token per-turn ceiling stop that. v2 gave grounded numbers with wrong reasoning; the tools now return their comparisons precomputed and dataset v3 teaches the model to copy them. v3 still chained unrelated tools when Ollama sent the 21 tool schemas, because it was trained without them; the presentation path now sends no schemas and parses the model's <tool_call> text, exactly as in training. Training and inference also share one 4,500-character tool-output cap, and the five presentation scenarios are held out of the training data.",
    )

    story.append(PageBreak())

    # ── Group 4 — Metrics ─────────────────────────────────────────────────────
    story += section("Group 4: §30 Evaluation Metrics")

    story += qa(
        'Q10. Is the fine-tuned model better than the base model?',
        "On the path the presentation uses, yes: without tool schemas the base never calls a tool and 7 of its 20 eval answers contain invented figures; the fine-tune calls the planned tool in 19 of 20 and one answer is ungrounded. With Ollama's tool schemas the base 3B is the stronger agent (invalid-call rate 0.05 vs 0.45) because the fine-tune was trained without schemas. That is why ask.py and the scenario runner use the training format.",
    )
    story += qa(
        'Q11. Why did the fine-tune regress on some metrics?',
        "Three reasons, all in outputs/training/base_vs_finetuned.md. (1) Over-caution: it labels ANALYSIS_UNSAFE too often outside its five question types and once misapplied the gate. (2) Unknown-label tokens: it quotes gate and error codes such as HARD_BLOCK or INVALID_SYMBOL from tool outputs. (I also fixed an evaluator bug that counted valid labels in quotes as unknown; both models were rescored from their traces.) (3) Invalid calls under the schema protocol, explained in Q10. The base's 0.00 invalid-call rate on the presentation protocol is vacuous: it never calls a tool.",
    )
    story += qa(
        'Q12. Given those regressions, why submit the fine-tune?',
        "Because the target behaviour, answering a user question from tool evidence without inventing numbers, only works with the fine-tune on the local presentation path: 5 of 5 scenario traces chose the right tool and every figure is grounded, while the base invents figures on that path. The regressions are documented with their causes, and the grounding audit is shown next to every live answer.",
    )

    # ── Group 5 — Methodology ─────────────────────────────────────────────────
    story += section("Group 5: Methodology & Background")

    story += qa(
        "Q13. What is TMS 29 and why does it affect your project?",
        "TMS 29 (Türkiye Muhasebe Standardı 29) is the Turkish implementation of IAS 29 — "
        "financial reporting in hyperinflationary economies. Starting from fiscal year 2024, "
        "BIST companies adjust their financial statements for inflation. This means FY2024+ "
        "financial statements are on an inflation-adjusted basis that is not directly comparable "
        "to pre-2024 nominal TRY statements. The project addresses this by using exclusively "
        "post-TMS29 data (2025–2026) for the fundamental layer — the gate hard-blocks "
        "PERIOD_MISMATCH if the model tries to mix pre/post-TMS29 statements.",
    )
    story += qa(
        "Q14. How do you ensure no look-ahead bias in the backtest?",
        "Four mechanisms: (1) Release-date exclusion — financials only enter the model after "
        "the first stock session strictly after the Fintables publication date. (2) Pivot "
        "right-window confirmation — a support/resistance level only becomes valid after the "
        "confirming right-window is fully observed (not while it is forming). (3) Price-future "
        "perturbation test — a test verifies that modifying future prices does not change past "
        "orders. (4) Dated comparative revisions — a later filing's correction to an earlier "
        "period only enters the model after the later filing's publication date.",
    )
    story += qa(
        "Q15. Why THYAO.IS (Turkish Airlines) as the primary study?",
        "THYAO is analytically interesting for three reasons: (1) High aircraft lease-related "
        "debt — requires a different leverage threshold (4× EBITDA declared as airline assumption "
        "vs 2× for other sectors). (2) International operations and USD/TRY currency sensitivity. "
        "(3) High liquidity and analyst coverage, so there is sufficient KAP event data. "
        "The user selected it and the project preserved it as the 'one deeply worked example' "
        "per the original project scope, while the 10-ticker scenario studies and the 18-ticker agent universe show it generalises.",
    )
    story += qa(
        "Q16. Why use a 4× net-debt/EBITDA leverage threshold specifically for airlines?",
        "Aircraft financing makes airline balance sheets structurally more leveraged than typical "
        "industrials. A 2× threshold (the default for the other 4 sectors) would nearly always "
        "fail airlines regardless of financial health. The 4× threshold is a declared assumption — "
        "not an industry-validated cutoff — and is documented in DECISIONS.md item 9 as an "
        "explicit airline case-study choice. A 2× variant was also run as a sensitivity check. "
        "EBITDA is not EBITDAR (it does not add back lease costs), which is a limitation noted "
        "in the documentation.",
    )

    story.append(PageBreak())

    # ── Group 6 — Scenarios & Results ─────────────────────────────────────────
    story += section("Group 6: Scenarios, Results & Future Work")

    story += qa(
        "Q17. What are the 4 mandatory scenario studies and what did each find?",
        "S1 Sector Laggards: used rank_sector_relative_strength to find stocks lagging their "
        "sector median. 92 weekly anchors across 5 sectors; the laggard beat its sector peers "
        "over 20 days 60.9% of the time in steel, 54.3% in banking and 44.6% in airlines. — "
        "S2 Weekday Patterns: used test_weekday_pattern to identify day-of-week return biases. "
        "No universal weekday edge; pattern significance varied by ticker. — "
        "S3 Reversal Events: used detect_reversal_events to flag technical bounces. 1,458 events; "
        "BB lower-touch and RSI oversold recovery bounced within 5 days 58.7% and 59.1% of the time. — "
        "S4 Fundamental Reaction: used calculate_fundamental_change to link QoQ changes to "
        "post-announcement price moves. THYAO.IS only: 7 release dates (19 panel rows).",
    )
    story += qa(
        'Q18. How does the model handle unsafe questions (future dates, unknown tickers)?',
        "check_data_quality returns HARD_BLOCK (FUTURE_STATEMENT or PRICE_HISTORY_BROKEN) and the label must be ANALYSIS_UNSAFE. The fine-tune gets the clear cases right (q17, q18 and scenario S5, where a 2027 date returns DATE_OUT_OF_SNAPSHOT). Its weakness is the opposite direction: it calls the gate on 14 of 20 eval questions and over-applies ANALYSIS_UNSAFE, including q19 where INVESTIGATE was expected.",
    )
    story += qa(
        'Q19. If this ran live today on a new ticker, could it be used for trading?',
        f"No. It is a teaching aid. (1) Prices cover {F['tickers']} tickers; any other ticker is HARD_BLOCKed. (2) Fundamentals exist for THYAO only, 2025-2026. (3) A 3B model can attach a correct figure to the wrong stock; the grounding audit cannot catch that. (4) No RLHF; the 'no advice' rule rests on the prompt, labels and gate. (5) Backtests use nominal TRY returns.",
    )
    story += qa(
        'Q20. What would you improve given more time?',
        "(1) Train with the tool schemas present, so the model behaves the same under any tool-calling client. (2) Add examples outside the five question types (status, indicators, backtest) and cases where the gate says INVESTIGATE, to cure the over-caution. (3) Teach attribution: examples that cite a figure together with its ticker, and an audit that checks the pairing. (4) Inflation-adjusted returns. (5) More tickers with fundamentals.",
    )

    doc.build(story)


# ─────────────────────────────────────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    F.update(_facts())

    req_path    = OUTPUT_DIR / "requirements_report.pdf"
    slides_path = OUTPUT_DIR / "presentation_slides.html"
    qa_path     = OUTPUT_DIR / "qa_prep.pdf"

    print("Building requirements report ...")
    build_requirements_report(req_path)
    print(f"  -> {req_path}")

    print("Building presentation slides ...")
    build_presentation_slides(slides_path)
    print(f"  -> {slides_path}")

    print("Building Q&A prep document ...")
    build_qa_prep(qa_path)
    print(f"  -> {qa_path}")

    print(f"\nGenerated 3 deliverables in {OUTPUT_DIR}")
    print("  Open presentation_slides.html in a browser -> Ctrl+P -> Save as PDF for slides.")


if __name__ == "__main__":
    main()
