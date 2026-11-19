# Final harness human review

The fixed model was `gpt-6-luna` at low reasoning effort. All five stages answered the same case as of 25 September 2026.

## Automated result

| Stage | Numerical exactness | Evidence coverage | Temporal validity | Constraint compliance | Gate |
| --- | ---: | ---: | --- | --- | --- |
| Raw LLM | 0% | 0% | Fail | Pass | Reject |
| LLM + Tools | 100% | 100% | Pass | Pass | Pass |
| Tools + Stateful Harness | 100% | 100% | Pass | Pass | Pass |
| + Evidence/Quality Gate | 100% | 100% | Pass | Pass | Pass |
| + Memory + Human Review | 100% | 100% | Pass | Pass | Pass automated gate |

The raw model did not guess: it returned null for unavailable facts. Every tool-enabled stage returned the exact seven checked values, used all six required MCP tools, cited no uncalled tool, used the correct financial period and event timestamp, and avoided investment advice.

## Candidate for review

> Latest available trailing financial state is for the period ending 2026-06-30: revenue TRY 1,132,505 million, net profit TRY 112,059 million, and net debt TRY 620,378 million. At 2026-09-25 the rule signal was HOLD (trend_filter; not an executed order). From 2025-01-01 through 2026-09-26-exclusive, returns were combined -0.11029793916663655, technical 0.06421505249467252, buy-and-hold 0.05291060851497198, and BIST100 0.30850781608315225. The latest reviewed KAP context event available by the as-of date was the 2026-09-23 Boeing 737 MAX order (boeing-2026).

The full candidate and evidence are `memory_human_review.json` and `memory_human_review.jsonl`. Automated checks are in `memory_human_review.score.json`. Hashes and state transitions are in `state.json`.

## Human decision

Check the numerical evidence, whether `HOLD` is clearly described as a model action while flat, the limitations, and presentation suitability. Record the reviewer, date, `approve` or `reject`, and comments in `human_review.json`.
