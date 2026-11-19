"""Phase D: 8-label action space, evidence bundle, 5-state data-quality gate."""

import pytest

from bist_analytics.analysis.evidence import build_evidence_bundle, observation
from bist_analytics.analysis.gate import check_data_quality
from bist_analytics.schemas import (
    EDUCATIONAL_LABELS,
    GATE_STATES,
    AgentAnswer,
    EvidenceBundle,
    EvidenceItem,
)


def _bundle(**overrides) -> EvidenceBundle:
    observed = [observation("calculate_indicators", 0.5, as_of="2025-05-01", note="combined_score"),
                observation("calculate_scores", 4, as_of="2025-05-01", note="technical_score"),
                observation("run_backtest", {"cumulative_return": 0.12}, as_of="2025-05-01",
                             note="holdout 2025"),
                observation("get_fundamental_metrics", 7.5, as_of="2025-04-30", note="pe")]
    committed = list(observed)
    kwargs = dict(ticker="THYAO.IS", as_of="2025-05-15", observed=observed, committed=committed,
                  educational_label="TECHNICAL_REVERSAL_CANDIDATE", gate_status="PASS", reason="t")
    kwargs.update(overrides)
    return build_evidence_bundle(**kwargs)


def test_labels_and_gate_states_are_tuples_of_length_8_and_5():
    assert len(EDUCATIONAL_LABELS) == 8
    assert len(GATE_STATES) == 5
    for label in ["HOLD", "WATCH", "INVESTIGATE", "POTENTIAL_CATCH_UP_CANDIDATE",
                  "TECHNICAL_REVERSAL_CANDIDATE", "FUNDAMENTAL_IMPROVEMENT_CANDIDATE",
                  "REJECT_SIGNAL", "ANALYSIS_UNSAFE"]:
        assert label in EDUCATIONAL_LABELS


def test_gate_passes_when_evidence_is_complete_and_fresh():
    decision = check_data_quality(_bundle(), max_fundamental_age_days=230,
                                   as_of_boundary="2025-05-15")
    assert decision.status == "PASS"
    assert not decision.hard_blocks


def test_gate_hard_blocks_on_future_statement():
    bundle = _bundle(committed=[observation("calculate_indicators", 0.5, as_of="2026-01-01", note="combined_score")])
    decision = check_data_quality(bundle, as_of_boundary="2025-05-15")
    assert decision.status == "HARD_BLOCK"
    assert any("FUTURE_STATEMENT" in b for b in decision.hard_blocks)


def test_gate_hard_blocks_on_look_ahead_note():
    bundle = _bundle(committed=[observation("run_backtest", {"cumulative_return": 0.4},
                                             as_of="2025-05-01", note="look-ahead tuned on 2025 returns")])
    decision = check_data_quality(bundle, as_of_boundary="2025-05-15")
    assert decision.status == "HARD_BLOCK"
    assert any("LOOK_AHEAD" in b for b in decision.hard_blocks)


def test_gate_escalates_to_investigate_on_missing_required_tool():
    committed = [observation("calculate_indicators", 0.5, as_of="2025-05-01", note="combined_score")]
    bundle = _bundle(committed=committed)
    decision = check_data_quality(bundle, as_of_boundary="2025-05-15")
    assert decision.status == "INVESTIGATE"


def test_gate_marks_pass_with_warnings_when_bundle_has_warnings():
    bundle = _bundle(warnings=["Nominal TRY returns."])
    decision = check_data_quality(bundle, as_of_boundary="2025-05-15")
    assert decision.status == "PASS_WITH_WARNINGS"


def test_gate_respects_analysis_unsafe_label():
    bundle = _bundle(educational_label="ANALYSIS_UNSAFE")
    decision = check_data_quality(bundle, as_of_boundary="2025-05-15")
    assert decision.status == "ANALYSIS_UNSAFE"


def test_gate_escalates_on_stale_fundamentals():
    committed = [observation("calculate_indicators", 0.5, as_of="2025-05-01", note="combined_score"),
                 observation("calculate_scores", 4, as_of="2025-05-01", note="technical_score"),
                 observation("run_backtest", {}, as_of="2025-05-01", note="holdout 2025"),
                 observation("get_fundamental_metrics", 7.5, as_of="2023-05-01", note="pe")]
    bundle = _bundle(committed=committed)
    decision = check_data_quality(bundle, as_of_boundary="2025-05-15", max_fundamental_age_days=230)
    assert decision.status in {"INVESTIGATE", "HARD_BLOCK"}  # 2 years is beyond even 2x limit -> HARD_BLOCK


def test_evidence_item_rejects_unknown_fields():
    with pytest.raises(ValueError):
        EvidenceItem(evidence_id="x", source_tool="y", value=1, bogus=True)


def test_agent_answer_shape_is_strict_and_label_restricted():
    answer = AgentAnswer(question="q", ticker="THYAO.IS", as_of="2025-05-15",
                          educational_label="HOLD", gate_status="PASS",
                          committed_evidence_ids=["e1"], explanation="because")
    assert answer.educational_label == "HOLD"
    with pytest.raises(ValueError):
        AgentAnswer(question="q", ticker="THYAO.IS", as_of="2025-05-15",
                    educational_label="BUY", gate_status="PASS",
                    committed_evidence_ids=["e1"], explanation="x")
