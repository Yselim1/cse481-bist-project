# Base vs fine-tuned local LLM (§30 metrics)

## Original protocol

Original eval protocol: Ollama sends the 21 tool schemas, base system prompt, 12 KB tool-result cap, no RAG (same settings as the earlier v1 evaluation).

**Fine-tuned vs base: 1 improved, 3 tied, 4 regressed** (of 8 metrics).

| Metric | Direction | Base | Fine-tuned | Verdict |
|---|---|---|---|---|
| `invalid_tool_call_rate` | ↓ | 0.05 | 0.45 | regressed |
| `missing_required_tool_rate` | ↓ | 0.10 | 0.00 | improved |
| `label_mismatch_rate` | ↓ | 0.05 | 0.10 | regressed |
| `advice_leak_rate` | ↓ | 0.00 | 0.00 | tie |
| `unknown_label_emitted_rate` | ↓ | 0.05 | 0.20 | regressed |
| `ungrounded_answer_rate` | ↓ | 0.00 | 0.05 | regressed |
| `max_turns_exceeded_rate` | ↓ | 0.00 | 0.00 | tie |
| `reproducibility_rate` | ↑ | 1.00 | 1.00 | tie |

<details><summary>Per-question labels</summary>

| Q | Scenario | Expected label | Base label | Fine-tuned label | Fine-tuned tools |
|---|---|---|---|---|---|
| q01 | status | — | — | — | project_status, generate_signal, generate_report, build_evidence_bundle, generate_signal |
| q02 | indicators | — | — | — | calculate_indicators, generate_signal, calculate_scores, generate_signal |
| q03 | scores | — | — | — | calculate_scores, generate_signal, calculate_indicators, generate_signal, calculate_scores, calculate_scores, calculate_scores, generate_signal |
| q04 | signal | HOLD|WATCH|INVESTIGATE|POTENTIAL_CATCH_UP_CANDIDATE|TECHNICAL_REVERSAL_CANDIDATE|FUNDAMENTAL_IMPROVEMENT_CANDIDATE|REJECT_SIGNAL|ANALYSIS_UNSAFE | INVESTIGATE | INVESTIGATE | get_fundamental_metrics, calculate_indicators, calculate_scores, generate_signal, check_data_quality |
| q05 | signal | any | INVESTIGATE | ANALYSIS_UNSAFE | calculate_indicators, calculate_scores, generate_signal, check_data_quality |
| q06 | sector_lag | — | — | POTENTIAL_CATCH_UP_CANDIDATE | rank_sector_relative_strength |
| q07 | sector_lag | — | — | POTENTIAL_CATCH_UP_CANDIDATE | rank_sector_relative_strength, rank_sector_relative_strength, rank_sector_relative_strength |
| q08 | weekday | — | WATCH | INVESTIGATE | test_weekday_pattern, generate_signal, calculate_indicators, generate_signal, calculate_scores, generate_signal |
| q09 | weekday | — | WATCH | — | test_weekday_pattern, generate_signal, generate_report, build_evidence_bundle, generate_signal |
| q10 | reversal | — | TECHNICAL_REVERSAL_CANDIDATE | TECHNICAL_REVERSAL_CANDIDATE | detect_reversal_events |
| q11 | reversal | — | TECHNICAL_REVERSAL_CANDIDATE | — | detect_reversal_events, generate_signal, generate_signal, generate_signal |
| q12 | fundamental | — | FUNDAMENTAL_IMPROVEMENT_CANDIDATE | — | calculate_fundamental_change, generate_signal, build_evidence_bundle, generate_report, run_backtest, calculate_fundamental_change |
| q13 | fundamental | — | — | WATCH | get_fundamental_metrics, generate_signal, calculate_scores, generate_report, build_evidence_bundle, find_support_resistance, calculate_fundamental_change, get_macro_context, get_index_history |
| q14 | macro | — | — | HOLD | get_macro_context, generate_signal, generate_report, build_evidence_bundle |
| q15 | news | — | — | — | get_news_events, build_evidence_bundle, find_support_resistance, detect_reversal_events, generate_signal, generate_report, run_backtest, calculate_fundamental_change, find_support_resistance |
| q16 | backtest | — | — | — | run_backtest, generate_report, build_evidence_bundle, generate_signal, calculate_scores, calculate_fundamental_change, find_support_resistance, detect_reversal_events, rank_sector_relative_strength, get_fundamental_metrics |
| q17 | gate_unsafe | ANALYSIS_UNSAFE | ANALYSIS_UNSAFE | ANALYSIS_UNSAFE | calculate_indicators, generate_signal, check_data_quality |
| q18 | gate_unsafe | ANALYSIS_UNSAFE | ANALYSIS_UNSAFE | ANALYSIS_UNSAFE | check_data_quality, generate_signal, calculate_indicators, build_evidence_bundle, generate_report, check_data_quality, calculate_fundamental_change |
| q19 | gate_unsafe | INVESTIGATE | INVESTIGATE | ANALYSIS_UNSAFE | calculate_indicators, check_data_quality, generate_signal, calculate_indicators, check_data_quality |
| q20 | evidence_bundle | HOLD | INVESTIGATE | INVESTIGATE | calculate_indicators, calculate_scores, run_backtest, get_fundamental_metrics, build_evidence_bundle |

</details>

## Presentation protocol

Presentation protocol: no schemas (the model writes `<tool_call>` text, as in its fine-tuning data), presentation system prompt, RAG context, 4.5 KB cap; the settings of `scripts/ask.py` and the five scenario traces.

**Fine-tuned vs base: 2 improved, 3 tied, 3 regressed** (of 8 metrics).

| Metric | Direction | Base | Fine-tuned | Verdict |
|---|---|---|---|---|
| `invalid_tool_call_rate` | ↓ | 0.00 | 0.10 | regressed |
| `missing_required_tool_rate` | ↓ | 1.00 | 0.05 | improved |
| `label_mismatch_rate` | ↓ | 0.05 | 0.10 | regressed |
| `advice_leak_rate` | ↓ | 0.00 | 0.00 | tie |
| `unknown_label_emitted_rate` | ↓ | 0.25 | 0.45 | regressed |
| `ungrounded_answer_rate` | ↓ | 0.35 | 0.05 | improved |
| `max_turns_exceeded_rate` | ↓ | 0.00 | 0.00 | tie |
| `reproducibility_rate` | ↑ | 1.00 | 1.00 | tie |

<details><summary>Per-question labels</summary>

| Q | Scenario | Expected label | Base label | Fine-tuned label | Fine-tuned tools |
|---|---|---|---|---|---|
| q01 | status | — | — | ANALYSIS_UNSAFE | check_data_quality |
| q02 | indicators | — | — | INVESTIGATE | calculate_indicators, check_data_quality |
| q03 | scores | — | — | INVESTIGATE | calculate_scores |
| q04 | signal | HOLD|WATCH|INVESTIGATE|POTENTIAL_CATCH_UP_CANDIDATE|TECHNICAL_REVERSAL_CANDIDATE|FUNDAMENTAL_IMPROVEMENT_CANDIDATE|REJECT_SIGNAL|ANALYSIS_UNSAFE | ANALYSIS_UNSAFE | ANALYSIS_UNSAFE | generate_signal, check_data_quality |
| q05 | signal | any | INVESTIGATE | ANALYSIS_UNSAFE | calculate_indicators, calculate_scores, generate_signal, check_data_quality, explanation |
| q06 | sector_lag | — | — | POTENTIAL_CATCH_UP_CANDIDATE | rank_sector_relative_strength |
| q07 | sector_lag | — | — | POTENTIAL_CATCH_UP_CANDIDATE | rank_sector_relative_strength |
| q08 | weekday | — | ANALYSIS_UNSAFE | ANALYSIS_UNSAFE | test_weekday_pattern, check_data_quality |
| q09 | weekday | — | REJECT_SIGNAL | INVESTIGATE | test_weekday_pattern, check_data_quality, calculate_indicators, calculate_fundamental_change, generate_signal |
| q10 | reversal | — | — | TECHNICAL_REVERSAL_CANDIDATE | detect_reversal_events |
| q11 | reversal | — | INVESTIGATE | TECHNICAL_REVERSAL_CANDIDATE | detect_reversal_events, calculate_indicators, calculate_scores, check_data_quality |
| q12 | fundamental | — | ANALYSIS_UNSAFE | INVESTIGATE | calculate_fundamental_change, check_data_quality |
| q13 | fundamental | — | — | ANALYSIS_UNSAFE | get_fundamental_metrics |
| q14 | macro | — | — | ANALYSIS_UNSAFE | get_macro_context |
| q15 | news | — | — | INVESTIGATE | get_news_events, check_data_quality |
| q16 | backtest | — | — | ANALYSIS_UNSAFE | run_backtest, check_data_quality |
| q17 | gate_unsafe | ANALYSIS_UNSAFE | ANALYSIS_UNSAFE | ANALYSIS_UNSAFE | calculate_indicators, generate_signal, check_data_quality |
| q18 | gate_unsafe | ANALYSIS_UNSAFE | ANALYSIS_UNSAFE | ANALYSIS_UNSAFE | check_data_quality |
| q19 | gate_unsafe | INVESTIGATE | INVESTIGATE | ANALYSIS_UNSAFE | check_data_quality, calculate_indicators |
| q20 | evidence_bundle | HOLD | ANALYSIS_UNSAFE | ANALYSIS_UNSAFE | calculate_indicators, calculate_scores, run_backtest, get_fundamental_metrics, build_evidence_bundle, check_data_quality |

</details>

## Earlier fine-tune (v1) for reference

Same 20 questions and original protocol; the v1 adapter was trained on dataset v1 and is not part of the submission. v1 numbers are as recorded at the time, before the unknown-label tokenizer fix, so their unknown-label rates are overstated.

| Metric | Base (Ollama default ctx) | v1 fine-tune | v3 fine-tune (submitted) |
|---|---|---|---|
| `invalid_tool_call_rate` | 0.45 | 0.45 | 0.45 |
| `missing_required_tool_rate` | 0.05 | 0.05 | 0.00 |
| `label_mismatch_rate` | 0.00 | 0.20 | 0.10 |
| `advice_leak_rate` | 0.00 | 0.00 | 0.00 |
| `unknown_label_emitted_rate` | 0.05 | 0.30 | 0.20 |
| `reproducibility_rate` | 1.00 | 1.00 | 1.00 |

## Reading the results (written 2026-11-25 from the traces above)

**On the path the presentation uses, the fine-tune is the model that works.** Without tool
schemas the base model never calls a tool (required-tool miss rate 1.00) and writes figures
from memory: 7 of its 20 answers contain numbers no tool returned (ungrounded rate 0.35; 17
unsupported figures in the q08 weekday answer alone). The fine-tune calls the planned tool in
19 of 20 questions and one answer (q04, two figures) is ungrounded.

**With Ollama's tool schemas, the base 3B is the stronger agent.** The fine-tune was trained
without schemas; given them, it calls the right tool first and then keeps going (invalid-call
rate 0.45 vs 0.05: extra `generate_signal` / `generate_report` / `build_evidence_bundle`
calls with bad arguments). One answer (q14, macro context) contains 43 ungrounded figures.
This is why `ask.py` and the scenario runner use the training format.

**The fine-tune is over-cautious outside its five question types.** On the presentation
protocol it labelled 11 of 20 answers ANALYSIS_UNSAFE, although only q17 and q18 are unsafe
cases (the base did so 6 times). It adds a `check_data_quality` call to 14 of 20 questions
and sometimes misapplies the gate: on q08 the gate returned INVESTIGATE and the answer still
said ANALYSIS_UNSAFE. Most of these questions have no expected label, so
`label_mismatch_rate` (0.10) does not show this; it is the clearest weakness in this eval.
Its expected-label misses are q19 (INVESTIGATE expected, ANALYSIS_UNSAFE given) and q20
(HOLD expected).

**Unknown-label tokens are mostly tool vocabulary.** After the tokenizer fix (labels in
quotes or followed by `;`/`:` were miscounted before, for both models and for the v1 run),
the fine-tune's remaining hits are gate and error codes it quotes from tool outputs:
HARD_BLOCK, PASS_WITH_WARNINGS, INVALID_SYMBOL, PRICE_HISTORY_BROKEN, FUTURE_STATEMENT.

**What the 20-question set does and does not measure.** Every question names the tool to
call. Eleven fall inside the fine-tuned question types (sector, weekday, reversal,
fundamental, unsafe: q06–q13, q17–q19); nine ask for general tool output the fine-tune was
not trained on (status, indicators, scores, signal, macro, news, backtest, evidence bundle). The five presentation scenarios, phrased the way a
user would ask and never naming a tool, are a better test of the target behaviour: there the
fine-tune chose the intended tool and gave a fully grounded answer in 5 of 5
(`outputs/presentation/traces/`).

## Metric definitions

- `invalid_tool_call_rate`: share of questions where at least one MCP call returned an error.
- `missing_required_tool_rate`: share missing at least one tool from the question's plan.
- `label_mismatch_rate`: share whose label is outside the expected set (questions without an expected label pass vacuously).
- `advice_leak_rate`: share containing banned advisory phrases.
- `unknown_label_emitted_rate`: share emitting an UPPER_SNAKE token outside the 8 labels (also catches quoted tool identifiers such as BB_LOWER_TOUCH).
- `ungrounded_answer_rate`: share whose answer contains a figure the grounding audit could not trace to a tool output (`src/bist_analytics/harness/grounding.py`).
- `max_turns_exceeded_rate`: share that hit the 15-turn limit without an answer.
- `reproducibility_rate`: share producing a non-empty final answer.

Both models: temperature 0, seed 17, 16k context (`training/Modelfile.base` builds `bist-qwen-base` from `qwen2.5:3b-instruct` with the fine-tune's context and sampling settings). Per-question traces: `outputs/harness/eval_v3/traces/`. Chart: `outputs/training/figures/base_vs_finetuned.png`.
