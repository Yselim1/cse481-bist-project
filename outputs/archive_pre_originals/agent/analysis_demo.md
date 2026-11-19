## THYAO.IS — as of 2025-12-31

**Current rule signal: HOLD with `holding=false`**, meaning remain out of the position. `generate_signal` identifies **`trend_filter`** as the reason; hypothetical execution uses the next available stock-session open.

### Evidence

- **Technical:** The actual market session is **2025-12-31**. Close was **268.50 TRY**, below fast/slow SMAs of **271.1625 / 276.64 TRY**. RSI was **42.6210**, MACD histogram **−0.0781**, and relative volume **0.6947**, consistent with weak trend and momentum. Support/resistance were **267.75 / 269.8642 TRY**; the tool reported no active zone membership. Sources: `get_stock_history`, `calculate_indicators`, `find_support_resistance`.
- **Fundamental:** The financial period used was **2024-12-31**, with modeled availability **2025-07-01**. Fintables-displayed **USD** revenue was **22,740,276,000** and net profit **3,458,738,000**. Revenue growth was **0.0682**, but profit growth **−0.4973**. Net debt/EBITDA was **1.6164** and P/E **2.4941**. Growth figures are decimal ratios. Source: `get_fundamental_metrics`.
- **Scores:** Technical **2.0**, fundamental **1.0 (“weak”)**, combined **0.32**. Only leverage earned fundamental points; RSI and support earned technical points. Source: `calculate_scores`.

### Backtest

Requested **2023-01-01 ≤ date < 2026-01-01**; actual coverage **2023-01-02–2025-12-31**. Values below are tool outputs rounded for display; returns, drawdowns, and win rates remain **decimal ratios**.

| Strategy / baseline | Cumulative return | Max drawdown | Sharpe, zero risk-free | Closed-trade win rate |
|---|---:|---:|---:|---:|
| Combined | 0.2624 | −0.1081 | 0.6331 | 0.6250 |
| Technical | 0.6119 | −0.1316 | 0.9950 | 0.6364 |
| THYAO buy-and-hold | 0.9273 | −0.2561 | 0.7504 | Unavailable |
| BIST100 | 1.0224 | −0.2286 | 0.9652 | Unavailable |

Sources: `run_backtest`, `generate_report`. Combined and technical strategies reduced drawdown but returned less than both baselines. Closed trades numbered **8** and **11**, respectively; buy-and-hold had **0** closed trades and **1** open trade.

**Costs and interpretation:** Results are net nominal **TRY**, with zero cash yield. Commission/slippage totals in TRY were **1,770.56 / 885.29** for combined, **3,123.48 / 1,561.75** for technical, and **99.90 / 49.93** for buy-and-hold. BIST100 carries no costs and uses a price-index basis, unlike the adjusted synthetic stock series. Taxes and whole-lot execution are unmodeled. Stock strategies cover **749** sessions; BIST100 covers **746**, with **3** missing sessions.

**Historical assumptions:** All **102** financial observations have unverified vintages; **68** use assumed release dates, with a following-June-30 convention. Modeled availability is not verified publication timing. These are retrospective results susceptible to revision and selection/survivorship bias, **not point-in-time validation or investment advice**. Missing values are unavailable, not zero.

`generate_report` returned the existing local report: [report.md](C:/Users/yavuz/Desktop/CSE481-Term-Project/outputs/retrospective/report.md).