"""Report numbers are rendered from the same saved Python results used by MCP."""

import os
from html import escape
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parents[2]/".cache/matplotlib"))
import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def md_table(frame: pd.DataFrame) -> str:
    values = frame.fillna("Unavailable").astype(str)
    return "| " + " | ".join(values.columns) + " |\n| " + " | ".join(["---"]*len(values.columns)) + " |\n" + "\n".join("| "+" | ".join(row)+" |" for row in values.to_numpy())


def fmt(value, percent=False):
    if value is None or pd.isna(value):
        return "Unavailable"
    return f"{value*100:.2f}%" if percent else f"{value:,.2f}"


def performance_table(performance):
    return pd.DataFrame([{"Strategy":name,"Return":fmt(m["cumulative_return"],True),
        "Max drawdown":fmt(m["maximum_drawdown"],True),"Sharpe (rf=0)":fmt(m["sharpe_zero_risk_free"]),
        "Closed trades":m.get("closed_trades","—"),"Win rate":fmt(m.get("win_rate"),True),
        "Exposure":fmt(m.get("exposure"),True),"Sessions":m["sessions"]} for name,m in performance.items()])


def create_report(analysis, performance, results, reference, periods, output: Path):
    cfg = analysis.config
    start_label = str(cfg.evaluation_start)
    end_label = str(pd.Timestamp(cfg.evaluation_end).date() - pd.Timedelta(days=1))
    is_tms29 = cfg.fundamentals_file.endswith("fintables_tms29_observations.csv")
    plt.rcParams.update({"figure.dpi":130,"axes.spines.top":False,"axes.spines.right":False,
                         "axes.grid":True,"grid.alpha":.2,"font.size":10,"savefig.facecolor":"white"})
    figures = output/"figures"
    figures.mkdir(exist_ok=True)
    colors = {"combined":"#be123c","technical":"#2563eb","buy_hold":"#15803d","bist100":"#6b7280"}
    fig,axes = plt.subplots(2,1,figsize=(11,7),sharex=True,gridspec_kw={"height_ratios":[2,1]},layout="constrained")
    for name,result in results.items():
        equity = result.daily.equity
        axes[0].plot(equity.index,equity/cfg.initial_capital*100,label=name,color=colors[name])
        peaks = np.maximum.accumulate(np.r_[cfg.initial_capital,equity.to_numpy()])[1:]
        axes[1].plot(equity.index,(equity/peaks-1)*100,color=colors[name],label=name)
    axes[0].plot(reference.index,reference/cfg.initial_capital*100,label="BIST100 price index",color=colors["bist100"],linestyle="--")
    axes[0].set(title=f"THYAO | {start_label}–{end_label} | {cfg.output_name}",ylabel="Initial capital = 100")
    axes[1].set(ylabel="Drawdown (%)")
    axes[0].legend(ncol=2)
    fig.savefig(figures/"performance.png")
    plt.close(fig)
    data = analysis.features.loc[start_label:]
    fig,axes = plt.subplots(3,1,figsize=(11,8),sharex=True,gridspec_kw={"height_ratios":[2,1,1]},layout="constrained")
    for col,color,label in [("close","#172554","Adjusted close"),("sma_fast","#d97706","SMA20"),("sma_slow","#2563eb","SMA50")]:
        axes[0].plot(data.index,data[col],label=label,color=color,lw=1.2)
    axes[0].scatter(data.index,data.support,label="Causal support",s=4,color="#15803d",alpha=.4)
    axes[0].scatter(data.index,data.resistance,label="Causal resistance",s=4,color="#be123c",alpha=.4)
    axes[0].set(title=f"Technical evidence from {start_label} | levels known at each close",ylabel="Adjusted TRY")
    axes[0].legend(ncol=3,fontsize=8)
    axes[1].plot(data.index,data.rsi,color="#7c3aed")
    axes[1].axhline(35,color="gray",ls=":")
    axes[1].axhline(55,color="gray",ls=":")
    axes[1].axhline(70,color="red",ls=":")
    axes[1].set(ylabel="RSI14",ylim=(0,100))
    axes[2].plot(data.index,data.macd,label="MACD",color="#2563eb")
    axes[2].plot(data.index,data.macd_signal,label="Signal",color="#d97706")
    axes[2].bar(data.index,data.macd_histogram,color="#94a3b8",width=1)
    axes[2].legend()
    fig.savefig(figures/"technical.png")
    plt.close(fig)
    fig,axes = plt.subplots(2,1,figsize=(11,5),sharex=True,layout="constrained")
    data = analysis.features.loc[start_label:]
    axes[0].step(data.index,data.fundamental_score,label="F score",color="#be123c",where="post")
    axes[0].plot(data.index,data.technical_score,label="T score",color="#2563eb",alpha=.45,lw=.8)
    axes[0].set(ylabel="Score / 5",ylim=(-.1,5.3),title="Historical score availability and combined rule")
    axes[0].legend()
    axes[1].plot(data.index,data.combined_score,color="#172554")
    axes[1].axhline(cfg.strategy.entry_score,color="#be123c",ls="--")
    axes[1].set(ylabel="Combined / 1",ylim=(0,1))
    fig.savefig(figures/"scores.png")
    plt.close(fig)
    tables = performance_table(performance)
    tables.to_csv(output/"performance_table.csv",index=False)
    annual_table = pd.DataFrame([{"Year":year,"Role":("primary (partial)" if int(year) == cfg.evaluation_end.year else "primary") if is_tms29 else {"2023":"development","2024":"validation","2025":"holdout"}.get(year,"evaluation"),
        "Combined return":fmt(p["combined"]["cumulative_return"],True),
        "Technical return":fmt(p["technical"]["cumulative_return"],True),
        "Buy/hold return":fmt(p["buy_hold"]["cumulative_return"],True),
        "BIST100 return":fmt(p["bist100"]["cumulative_return"],True)} for year,p in periods.items()])
    latest = analysis.features.iloc[-1]
    financial_cols = ["revenue","gross_profit","ebitda","operating_profit","net_profit","cash","financial_debt","net_debt",
                      "total_assets","equity","operating_cash_flow","investing_cash_flow","financing_cash_flow"]
    financial_table = pd.DataFrame({"Metric":financial_cols,f"{cfg.fundamental_currency} millions":[fmt(latest.get(c,np.nan)/1e6) for c in financial_cols]})
    ratio_cols = ["revenue_growth","net_profit_growth","ebitda_growth","roe","roa","ebitda_margin","net_margin",
                  "net_debt_ebitda","debt_equity","current_ratio","quick_ratio","pe","pb","ev_ebitda"]
    ratio_table = pd.DataFrame({"Metric":ratio_cols,"Value":[fmt(latest.get(c,np.nan),i<7) for i,c in enumerate(ratio_cols)]})
    financial_table.to_csv(output/"financial_analysis.csv",index=False)
    ratio_table.to_csv(output/"ratio_analysis.csv",index=False)
    main = performance["combined"]
    comparison = main["benchmark_difference_pp"]
    findings = (f"The combined rule returned {fmt(main['cumulative_return'],True)} with a maximum drawdown of "
        f"{fmt(main['maximum_drawdown'],True)} and {main['closed_trades']} closed trades. Its endpoint return differed from "
        f"BIST100 by {fmt(comparison)} percentage points. Low activity is flagged rather than treated as evidence of robustness. "
        "These outcomes describe this dataset and frozen rule; they do not establish an investable advantage.")
    if cfg.vintage_policy == "verified_only" and not analysis.quality["fundamental_complete_sessions"]:
        findings = "The combined strategy remains in cash because the current financial vintages fail the source eligibility gate. Its zero return is not evidence of a successful trading strategy."
    notice = ("Retrospective research. Historical financial vintages are unverified. Some release dates are assumed. This report does not establish point-in-time investment performance."
              if cfg.vintage_policy == "retrospective" else
              ("Verified post-TMS 29 Fintables original statements. Current and comparative columns enter only after publication; academic backtest with the limitations below." if is_tms29 else
               "Verified annual Fintables original statements. Comparative revisions enter only after publication. Original TRY presentation; annual refresh; academic backtest with the limitations below."))
    gross_table = pd.DataFrame([{"Strategy":name,"Net return":fmt(row["cumulative_return"],True),
        "Gross, same executions":fmt(row["gross_return_same_executions"],True)} for name,row in performance.items() if name != "bist100"])
    sections = [
        ("1. Research question", "Does a publication-lagged Fintables financial filter change the behavior of a causal technical strategy for Turkish Airlines, compared with technical-only trading, stock buy-and-hold and the BIST100 price index?"),
        ("2. Scope and source quality", f"THYAO.IS; warm-up from {cfg.market_start}; evaluation {start_label} through {end_label}; initial capital TRY {cfg.initial_capital:,.0f}. "
         f"Fintables supplies {analysis.quality['fundamentals']['observations']} normalized observations over {len(analysis.quality['fundamentals']['periods'])} financial period ends. "
         f"Evaluation has {analysis.quality['evaluation_sessions']} stock sessions; {analysis.quality['fundamental_complete_sessions']} have all five fundamental score inputs. "
         "Historical values come exclusively from Fintables. See ../../docs/DATA_SOURCES.md and the run manifest for provenance. "
         f"The configured vintage policy is {cfg.vintage_policy}. Currency is {cfg.fundamental_currency}; source eligibility and revisions are documented in the manifest."),
        ("3. Method and timing", "SMA20/50 and EMA20/50 use trailing closes; EMA uses a simple-average seed. RSI14 uses Wilder smoothing; MACD is EMA12 minus EMA26 with a nine-period signal. "
         "Volume features include relative volume, change and OBV. A pivot needs five observations on either side and becomes usable only on its fifth following session. "
         "Confirmed prices from the trailing 252 sessions form clusters with maximum 1.5% width and at least two touches. No later pivot is painted into an earlier decision. "
         "Financial snapshots join backward after their verified or explicitly assumed release date. Annual totals are not fourth-quarter flows. Original-report comparative revisions enter at the containing report's publication, never at the earlier period end."),
        ("4. Fundamental analysis at the final stock date", f"The following values are the latest modeled available financial period on {analysis.features.index[-1].date()}: "
         + str(latest.get("financial_period"))+f". Flows are trailing totals when enough same-basis YTD/annual observations exist; assets and debt are period-end balances in {cfg.fundamental_currency}. "
         "EBITDA and net debt follow the formulas documented in DATA_SOURCES.md. Net profit is parent-attributable; average equity/assets are used for ROE/ROA. Valuation uses raw stock price and nominal shares, with same-date FX conversion only when using USD fundamentals. "
         "Growth against a loss or missing denominator is unavailable. Deferred-tax gains, airline cycles, leases and exchange translation can distort apparent profitability."),
        ("5. Explainable strategy", "Each technical and fundamental component contributes one point. Fundamental conditions: sales growth >15%, earnings growth >15%, ROE >20%, net debt/EBITDA <4, and positive P/E at or below its prior 252-valid-session median (minimum 63). "
         "Technical conditions: SMA20 > SMA50, RSI 35–55, MACD above signal, relative volume >=1, and within 2% of support or inside a confirmed zone. "
         "Combined score = .6*T/5 + .4*F/5. Entry additionally requires F>=3, combined>=.70, complete/fresh fundamentals, trend and support. "
         "Exit on a close-triggered 8% loss, 40-session holding limit, unavailable/stale/weak fundamentals, trend reversal or RSI>=70. Exits take precedence; the next session open executes each decision. "
         "The 4x leverage threshold is a predeclared airline case-study assumption, not an established sector optimum."),
        ("6. Evaluation", findings+" Both sides pay 10 bps commission and 5 bps slippage. Fractional adjusted-price units avoid double-counting dividends; final positions are marked at close. "
         "Win rate counts closed net-profitable trades only. Sharpe annualizes observed daily returns at 252 with zero risk-free return; maximum drawdown includes initial capital. "
         "The BIST100 reference has no transaction costs and is a price index. Missing index sessions stay missing; its risk-metric observation count is reported."),
        ("7. Chronological split", "Each calendar-year evaluation starts flat with TRY100,000 and retains the preceding feature warm-up. They are independent starts and need not compound to the full-period result. "
         "The strategy settings remain fixed across the displayed periods. A partial final year is labeled explicitly and is not compared as though it were a full year."),
        ("8. MCP AI agent", "The stdio MCP server wraps the same local Python analytics, with typed inputs, bounded symbols/dates, structured values and explicit source warnings. "
         "The host computes no financial numbers independently: it calls history, indicators, zones, fundamentals, scores, signals and backtest tools, then explains the evidence. "
         "An actual Codex host trace and final answer are stored in ../agent, including a missing-data demonstration. Protocol tests independently compare tool results with direct Python calculations. Tools never place trades."),
        ("9. Verification and limitations", "Unit tests independently check indicator recurrences, pivot confirmation, prefix invariance, release boundaries, later financial revisions, invalid denominators, next-open gaps, fees, position state and benchmark identities. "
         "These verify implementation behavior, not future investment performance. The original-report dataset has verified publication dates and separately dated comparatives; the earlier displayed-USD table study remains unverified. "
         "Further limits include one selected company, short evaluation, nominal TRY inflation, zero cash yield, simplistic slippage, fractional units, no taxes, unmatched benchmark return bases and index gaps. "
         "Original TRY accounts use nominal presentation and currency translation; their growth is not real growth or functional-USD growth. The original-report manifest includes page references, hashes and statement reconciliations."),
        ("10. Reproduction and follow-up", "For the primary study, run .venv/Scripts/python.exe -m bist_analytics.cli --config config/tms29.yaml import-tms29, fetch --refresh, and run. "
         "The report, data, trades, signals, charts, metrics and source/code hashes are regenerated locally. The annual baseline remains available through config/project.yaml, and the earlier displayed-USD study through config/retrospective.yaml.")]
    md = "# Turkish Airlines: technical and fundamental strategy study\n\n**CSE481 term project | 27 September 2026 | Educational research**\n\n"+notice+"\n\n"
    html_parts = []
    for title,text in sections:
        md += f"## {title}\n\n{text}\n\n"
        html_parts.append(f"<section><h2>{escape(title)}</h2><p>{escape(text)}</p>")
        add_tables = [financial_table,ratio_table] if title.startswith("4.") else [tables,gross_table] if title.startswith("6.") else [annual_table] if title.startswith("7.") else []
        for table in add_tables:
            md += md_table(table)+"\n\n"
            html_parts.append(table.to_html(index=False,border=0,escape=True))
        chart = "technical" if title.startswith("3.") else "scores" if title.startswith("5.") else "performance" if title.startswith("6.") else None
        if chart:
            md += f"![{chart}](figures/{chart}.png)\n\n"
            html_parts.append(f'<img src="figures/{chart}.png" alt="{chart} evidence chart">')
        html_parts.append("</section>")
    (output/"report.md").write_text(md,encoding="utf-8")
    (output/"report.html").write_text('''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>THYAO research report</title><style>
body{font:16px/1.65 system-ui,sans-serif;color:#172554;background:#f1f5f9;margin:0}main{max-width:1120px;margin:auto;background:white;padding:48px}h1{font-size:36px;line-height:1.15}h2{font-size:24px;margin-top:40px}p{max-width:100ch}header{border-top:8px solid #be123c;padding-top:18px}small{color:#475569}.notice{background:#fff1f2;padding:16px;border-left:4px solid #be123c}table{border-collapse:collapse;width:100%;font-size:14px;margin:24px 0}td,th{text-align:left;padding:10px;border-bottom:1px solid #cbd5e1}th{background:#f1f5f9}img{width:100%;height:auto}section{overflow-x:auto}@media(max-width:700px){main{padding:20px}h1{font-size:28px}}@media print{body{background:white}main{padding:0}section{break-inside:auto}img,table{break-inside:avoid}}
</style></head><body><main><header><small>CSE481 · TURKISH AIRLINES · 15 SEPTEMBER 2026</small><h1>Technical and fundamental strategy study</h1></header>
<p class="notice">'''+escape(notice)+"</p>"+"".join(html_parts)+"</main></body></html>",encoding="utf-8")
