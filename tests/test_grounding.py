from bist_analytics.harness.grounding import audit_answer, extract_figures


def test_extracts_figures_and_skips_dates_and_identifiers():
    figs = extract_figures("As of 2025-12-31, XU100 rose 4.2% and RSI was 61.37 in 2025.")
    texts = [f["text"] for f in figs]
    assert "4.2%" in texts and "61.37" in texts
    assert not any(t.startswith("12") or t == "100" for t in texts)
    assert next(f for f in figs if f["text"] == "2025")["is_year"]


def test_rounded_and_percent_values_are_grounded():
    evidence = [{"data": {"rsi_14": 61.3712, "ret": -0.04213, "pe": 3.87}}]
    audit = audit_answer("RSI 61.37, return -4.2%, P/E 3.9.", evidence)
    assert audit["all_grounded"], audit["ungrounded"]
    assert audit["grounded_count"] == 3


def test_fabricated_number_is_flagged():
    audit = audit_answer("Net profit grew 37.5% to 12,345.6 million TRY.", [{"x": 0.12}])
    assert not audit["all_grounded"]
    assert {f["text"] for f in audit["ungrounded"]} == {"37.5%", "12,345.6"}


def test_prompt_numbers_and_small_counts_are_not_ungrounded():
    audit = audit_answer("Over the 63-day lookback I used 3 tools.", [{}],
                         prompt_texts=["Use a lookback of 63 trading days."])
    assert audit["all_grounded"]
    assert audit["echoed_from_prompt"] == ["63"] and audit["small_integers"] == ["3"]


def test_numbers_inside_json_strings_count_as_evidence():
    audit = audit_answer("Mean forward return 1.25%.", ['{"mean_fwd_5d": 0.0125}'])
    assert audit["all_grounded"]


def test_sign_dropped_in_prose_is_abs_match():
    audit = audit_answer("The stock fell 4.2% versus its sector.", [{"gap": -0.042}])
    assert audit["all_grounded"] and audit["grounded"][0]["abs_match"]


def test_coarse_figure_is_not_grounded_by_rounding():
    # Regression: the model invented a "-5%" threshold; -4.82% must not ground it.
    audit = audit_answer("It sits at -0.0482, below -5%, so it is blocked.", [{"rel": -0.0481709}])
    assert [f["text"] for f in audit["ungrounded"]] == ["-5%"]


def test_coarse_figure_with_exact_tool_value_is_grounded():
    audit = audit_answer("Stop-loss is 8%.", [{"stop_loss": 0.08}])
    assert audit["all_grounded"]


def test_coarse_percent_does_not_match_a_bare_count():
    audit = audit_answer("Returns below -5% trigger a block.", [{"count": 5}])
    assert [f["text"] for f in audit["ungrounded"]] == ["-5%"]


def test_percent_in_evidence_text_grounds_percent_in_answer():
    audit = audit_answer("The stop-loss is 8%.", ["Frozen stop-loss of 8% per trade."])
    assert audit["all_grounded"]
