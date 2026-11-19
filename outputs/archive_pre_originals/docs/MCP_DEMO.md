# Real MCP agent demonstration

## Tested connection

On 15 September 2026, the authenticated **Codex CLI 0.154.0** host called this project's **MCP Python SDK 2.2.0** server over stdio using Python 3.12.14. The installed host used its account default model; no model identity is inferred from the output. The demonstration was a real model-to-tool session. `scripts/verify_mcp.py` is a separate protocol test and does not use an LLM.

The runner passes an ephemeral local MCP configuration and an explicit prompt to `codex exec`. It does not change global configuration or read authentication files. The host filesystem sandbox is read-only. All nine tools advertise read-only, idempotent, nondestructive, closed-world annotations. No function submits trades or contacts a broker.

## Tools and boundaries

| Tool | Evidence returned |
| --- | --- |
| `project_status` | Project scope, source policy, cached coverage |
| `get_stock_history` | THYAO adjusted/raw OHLCV, bounded date and row count |
| `calculate_indicators` | SMA, EMA, RSI, MACD, volume features at requested date |
| `find_support_resistance` | Confirmed pivots/zones and distances known by that date |
| `get_fundamental_metrics` | Financial values, ratios, source period, availability and missingness |
| `calculate_scores` | Individual points, totals and explanations |
| `generate_signal` | BUY/SELL/HOLD for supplied position state; no order submission |
| `run_backtest` | Combined, technical, buy-and-hold and BIST100 results |
| `generate_report` | Existing report path and saved results, explicitly dated |

THYAO.IS is the only accepted stock. The server restricts market requests to the cached 2021-2025 scope; history returns at most 252 rows. Backtest end dates are exclusive. Missing values become JSON nulls, not zero. Errors use MCP's tool-error response. Financial values are Fintables-displayed USD; trading/accounting values use nominal TRY.

## Captured evidence

| Demonstration | Actual saved evidence | Outcome |
| --- | --- | --- |
| Connection smoke test | `outputs/agent/smoke.jsonl`, `smoke.md` | `project_status` called successfully |
| Full financial analysis | `outputs/agent/analysis_demo.jsonl`, `analysis_demo.md` | All eight analysis tools called successfully |
| Missing/invalid data | `outputs/agent/missing_data.jsonl`, `missing_data.md` | Missing fundamentals explicitly null; invalid ticker rejected |
| Real stdio integration | `outputs/verification/mcp_protocol.json` | Nine tools discovered; eight checks including direct-Python equality |

JSONL files contain genuine host events and tool outputs. Markdown files are the host's actual final explanations. They form the offline backup demonstration. Replaying a saved trace must be described as a recording, not a new live model run. No screenshot is substituted for a tool call.

## Narrative audit

The full answer was checked against its tool responses and the saved data:

- Market date 2025-12-31, close 268.50 TRY, SMA20 271.1625, SMA50 276.64, RSI 42.6210, MACD histogram -0.0781, relative volume 0.6947: matches the indicator/history responses at displayed precision.
- Support 267.75 and resistance 269.8642; outside a zone: matches the level response.
- FY2024 revenue USD 22,740,276,000 and parent net profit USD 3,458,738,000; modeled available 2025-07-01: matches the financial response. Growth values 0.0682 and -0.4973 are explicitly decimal ratios.
- Net debt/EBITDA 1.6164, P/E 2.4941; T=2, F=1, combined=0.32; HOLD while flat with `trend_filter`: matches tools. HOLD is not a recommendation to retain a held stock.
- Four-strategy return, drawdown, Sharpe and win-rate table: matches `performance.json` to four decimals. Eight/eleven closed trades and the one open buy-and-hold position match the ledgers.
- Fees/slippage, 749/746 session counts, 102 unverified observations and 68 assumed-date observations: match source-quality and performance outputs.
- Missing-data answer: 2021-01-15 has no eligible fundamentals or warmed-up scores. The later report is correctly identified as 2023-2025 and is not passed off as a 2021 report.

No unsupported financial figure was found in these two saved explanations. The later fixed-execution gross-return field is an added deterministic result; it was not claimed in the earlier AI answer. Tests and source hashes accompany the final release.

`scripts/audit_agent_evidence.py` compares the recorded response fields with current Python and saves `outputs/verification/agent_evidence.json`. One metadata correction is documented: the early `run_backtest` envelope used the exclusive end date 2026-01-01 as `as_of`; the final server uses the actual last session 2025-12-31. The performance's own start/end dates, financial results and actual AI explanation already used the correct period. The original trace is preserved without editing. The offline viewer is `outputs/agent/recorded_demo.html`.

## Re-run

Follow README setup, then run `scripts/run_agent_demo.py --smoke`, `scripts/run_agent_demo.py`, or `scripts/run_agent_demo.py --missing` with the project Python. The user must be signed into the official Codex CLI. New model runs consume account usage. The runner checks for required successful MCP calls; an empty host answer or zero CLI exit code alone does not pass.

For another MCP-capable host, use the absolute project Python executable as `command`, `['-m', 'bist_analytics.mcp.server']` as `args`, and the project directory as the working directory. Keep SDK/version-specific host syntax in that host's configuration.

If startup fails, check the interpreter imports `bist_analytics` and `mcp`, and that it is the environment installed from `uv.lock`. If tools are blocked, inspect the host's tool approval UI and the read-only annotations; do not disable safeguards. Public Yahoo/Fintables access is unnecessary for cached demonstrations.
