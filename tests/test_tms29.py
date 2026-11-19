import json

import pandas as pd

from bist_analytics.config import load_config, project_root
from bist_analytics.data.context import CONTEXT_FILE, context_as_of, load_context_events
from bist_analytics.data.fundamentals import load_observations
from bist_analytics.data.tms29 import TMS29_FILE, normalize_tms29, verify_tms29_hashes
from bist_analytics.harness.evaluation import EXPECTED, REQUIRED_TOOLS, score_answer


def test_tms29_parser_reconciles_and_matches_reviewed_values():
    root = project_root()
    manifest = normalize_tms29(root)
    assert manifest["observations"] == 238
    assert all(abs(value) <= 1 for check in manifest["statement_checks"] for value in check["residuals_million_try"].values())
    records = load_observations(root/TMS29_FILE)
    latest = records[(records.period_end == pd.Timestamp("2026-06-30")) &
                     (records.published_at == pd.Timestamp("2026-08-05"))].set_index("metric").value
    assert latest["revenue"] == 585_069_000_000
    assert latest["net_profit"] == 18_864_000_000
    assert latest["financial_debt"] == 914_234_000_000
    assert latest["net_debt"] == 620_378_000_000
    verify_tms29_hashes(root)


def test_tms29_config_is_internally_consistent():
    config = load_config(project_root()/"config/tms29.yaml")
    assert config.evaluation_start.isoformat() == "2025-01-01"
    assert config.evaluation_end.isoformat() == "2026-09-26"
    assert config.fundamental_currency == "TRY"
    assert config.output_name == "tms29_primary"


def test_context_is_timestamp_bounded():
    events = load_context_events(project_root()/CONTEXT_FILE)
    before = context_as_of(events, "2026-09-23 18:18:59+03:00")
    after = context_as_of(events, "2026-09-23 18:19:00+03:00")
    assert "boeing-2026" not in set(before.event_id)
    assert "boeing-2026" in set(after.event_id)
    assert len(events) == 13


def test_quality_gate_requires_exact_facts_and_actual_tools():
    answer = {
        **{key: EXPECTED[key] for key in ["as_of", "financial_period", *[
            "revenue_try_million", "net_profit_try_million", "net_debt_try_million",
            "combined_return", "technical_return", "buy_hold_return", "bist100_return"], "signal_action"]},
        "context_event_ids": [EXPECTED["context_event_id"]], "evidence_tools": sorted(REQUIRED_TOOLS),
        "educational_caveat": "Academic evidence only.", "investment_recommendation": False,
    }
    assert score_answer(answer, set(REQUIRED_TOOLS))["quality_gate_pass"]
    answer["combined_return"] = 0.5
    assert not score_answer(answer, set(REQUIRED_TOOLS))["quality_gate_pass"]


def test_harness_memory_contains_source_and_context_constraints():
    memory = json.loads((project_root()/"data/harness/memory.json").read_text(encoding="utf-8"))
    assert "Fintables" in memory["source_constraint"]
    assert "never change" in memory["context_constraint"]
