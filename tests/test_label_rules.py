from bist_analytics.strategy import label_rules as lr


def test_sector_label_thresholds():
    assert lr.sector_label(-0.06) == "POTENTIAL_CATCH_UP_CANDIDATE"
    assert lr.sector_label(0.06) == "WATCH"
    assert lr.sector_label(-0.0482) == "HOLD"


def test_weekday_label_uses_screen_p_value():
    assert lr.weekday_label(0.05) == "INVESTIGATE"
    assert lr.weekday_label(0.37) == "WATCH"
    assert lr.weekday_label(None) == "WATCH"


def test_reversal_label_needs_min_events():
    assert lr.reversal_label(0.02, 2) == "TECHNICAL_REVERSAL_CANDIDATE"
    assert lr.reversal_label(0.02, 1) == "WATCH"
    assert lr.reversal_label(0.004, 9) == "WATCH"


def test_fundamental_label_net_profit_needs_revenue_growth():
    assert lr.fundamental_label("net_profit_qoq", 0.2, 0.05) == "FUNDAMENTAL_IMPROVEMENT_CANDIDATE"
    assert lr.fundamental_label("net_profit_qoq", 0.2, -0.01) == "WATCH"
    assert lr.fundamental_label("revenue_qoq", -0.2, None) == "REJECT_SIGNAL"


def test_reversal_summary_groups_and_sorts():
    events = [{"event_type": "a", "forward_1d": 0.01, "forward_3d": 0.0, "forward_5d": 0.02},
              {"event_type": "a", "forward_1d": 0.03, "forward_3d": 0.0, "forward_5d": None},
              {"event_type": "b", "forward_1d": 0.0, "forward_3d": 0.0, "forward_5d": -0.01}]
    summary = lr.summarize_reversal_events(events)
    assert [s["event_type"] for s in summary] == ["a", "b"]
    assert summary[0]["count"] == 2 and summary[0]["n_forward_5d"] == 1
    assert summary[0]["mean_forward_1d"] == 0.02


def test_rule_text_matches_numeric_thresholds():
    assert str(lr.SECTOR_RULE["catch_up_below"]) in lr.SECTOR_RULE["rule"]
    assert str(lr.REVERSAL_RULE["candidate_above"]) in lr.REVERSAL_RULE["rule"]
    assert str(lr.WEEKDAY_RULE["bonferroni_p_threshold"]) in lr.WEEKDAY_RULE["rule"]
