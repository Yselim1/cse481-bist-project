# Scenario 2 — Weekday and multi-day patterns

Window: 2025-01-01 to 2026-11-01.

## Per-ticker weekday mean return (sorted by |t|)

| ticker | weekday | count | mean | win_rate | t_statistic | p_value_uncorrected |
| --- | --- | --- | --- | --- | --- | --- |
| PGSUS.IS | Wed | 91 | -0.0060 | 0.4066 | -2.5795 | 0.0099 |
| KRDMD.IS | Mon | 92 | 0.0062 | 0.5870 | 2.0624 | 0.0392 |
| EREGL.IS | Mon | 92 | 0.0044 | 0.5435 | 1.8647 | 0.0622 |
| THYAO.IS | Wed | 91 | -0.0042 | 0.4396 | -1.8368 | 0.0662 |
| TCELL.IS | Fri | 92 | -0.0040 | 0.4674 | -1.7038 | 0.0884 |
| EREGL.IS | Wed | 91 | -0.0041 | 0.4176 | -1.5831 | 0.1134 |
| AKBNK.IS | Mon | 92 | 0.0041 | 0.5435 | 1.5540 | 0.1202 |
| PGSUS.IS | Tue | 92 | -0.0034 | 0.3696 | -1.5334 | 0.1252 |
| GARAN.IS | Mon | 92 | 0.0034 | 0.4783 | 1.3162 | 0.1881 |
| BIMAS.IS | Fri | 92 | -0.0028 | 0.4239 | -1.2682 | 0.2047 |
| BIMAS.IS | Tue | 92 | 0.0030 | 0.5109 | 1.2561 | 0.2091 |
| BIMAS.IS | Wed | 91 | 0.0027 | 0.5385 | 1.0938 | 0.2740 |
| TCELL.IS | Thu | 90 | 0.0022 | 0.4778 | 1.0632 | 0.2877 |
| EREGL.IS | Thu | 90 | 0.0022 | 0.5000 | 1.0069 | 0.3140 |
| TCELL.IS | Tue | 92 | 0.0020 | 0.5543 | 0.8866 | 0.3753 |
| MGROS.IS | Tue | 92 | -0.0016 | 0.4457 | -0.8041 | 0.4213 |
| AKBNK.IS | Fri | 92 | -0.0022 | 0.4783 | -0.7751 | 0.4383 |
| TTKOM.IS | Mon | 92 | 0.0018 | 0.5326 | 0.7543 | 0.4507 |
| THYAO.IS | Fri | 92 | 0.0015 | 0.5217 | 0.7306 | 0.4650 |
| PGSUS.IS | Thu | 90 | 0.0014 | 0.5222 | 0.7165 | 0.4737 |

## Multi-day pattern (horizon=3) — top 20 by |t|

| ticker | weekday | count | mean | win_rate | t_statistic | p_value_uncorrected |
| --- | --- | --- | --- | --- | --- | --- |
| PGSUS.IS | Mon | 92 | -0.0080 | 0.4022 | -1.9972 | 0.0458 |
| PGSUS.IS | Tue | 92 | -0.0067 | 0.4022 | -1.8107 | 0.0702 |
| BIMAS.IS | Tue | 92 | 0.0070 | 0.5652 | 1.7576 | 0.0788 |
| BIMAS.IS | Mon | 92 | 0.0078 | 0.5652 | 1.7346 | 0.0828 |
| EREGL.IS | Thu | 90 | 0.0069 | 0.6111 | 1.4556 | 0.1455 |
| TCELL.IS | Tue | 92 | 0.0046 | 0.5217 | 1.3423 | 0.1795 |
| KRDMD.IS | Thu | 90 | 0.0062 | 0.5556 | 1.1907 | 0.2338 |
| EREGL.IS | Fri | 91 | 0.0045 | 0.5495 | 0.9405 | 0.3470 |
| GARAN.IS | Mon | 92 | 0.0044 | 0.5978 | 0.9347 | 0.3499 |
| KRDMD.IS | Fri | 91 | 0.0047 | 0.6044 | 0.9327 | 0.3510 |
| TCELL.IS | Mon | 92 | 0.0033 | 0.4891 | 0.9265 | 0.3542 |
| KRDMD.IS | Mon | 92 | 0.0045 | 0.5543 | 0.8596 | 0.3900 |
| PGSUS.IS | Thu | 90 | 0.0030 | 0.5000 | 0.8171 | 0.4139 |
| GARAN.IS | Wed | 90 | -0.0037 | 0.4333 | -0.7992 | 0.4242 |
| THYAO.IS | Fri | 91 | 0.0030 | 0.5055 | 0.7762 | 0.4376 |
| PGSUS.IS | Wed | 90 | -0.0030 | 0.4556 | -0.7687 | 0.4421 |
| AKBNK.IS | Wed | 90 | -0.0040 | 0.4556 | -0.7186 | 0.4724 |
| AKBNK.IS | Fri | 91 | 0.0033 | 0.4945 | 0.6958 | 0.4866 |
| GARAN.IS | Fri | 91 | 0.0029 | 0.5275 | 0.6826 | 0.4949 |
| THYAO.IS | Wed | 90 | -0.0023 | 0.4889 | -0.6552 | 0.5124 |

**Caveat.** p-values are uncorrected for multiple testing across tickers and weekdays; treat sub-5% flags as hypotheses to investigate, not trading rules.