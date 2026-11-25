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
