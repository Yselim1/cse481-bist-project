"""Render the existing analysis and verification evidence into a printable PDF."""

import json
import os
from html import escape
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR",str(ROOT/".cache/matplotlib"))

OUT = ROOT/"outputs/verified_only"
WIDTH = A4[0]-88


def safe(text):
    return escape(str(text).replace("–","-").replace("—","-").replace("−","-"))


def main():
    from matplotlib import font_manager

    pdfmetrics.registerFont(TTFont("Body",font_manager.findfont("DejaVu Sans")))
    pdfmetrics.registerFont(TTFont("Bold",font_manager.findfont(font_manager.FontProperties(family="DejaVu Sans",weight="bold"))))
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Text",fontName="Body",fontSize=9.2,leading=13.8,spaceAfter=9,textColor=colors.HexColor("#172554")))
    styles.add(ParagraphStyle(name="Heading",fontName="Bold",fontSize=21,leading=26,spaceAfter=18,textColor=colors.HexColor("#172554")))
    styles.add(ParagraphStyle(name="Sub",fontName="Bold",fontSize=12,leading=16,spaceBefore=12,spaceAfter=8,textColor=colors.HexColor("#be123c")))
    styles.add(ParagraphStyle(name="SmallText",fontName="Body",fontSize=7.5,leading=10,spaceAfter=5))
    soup = BeautifulSoup((OUT/"report.html").read_text(encoding="utf-8"),"html.parser")
    sections = {int(section.h2.text.split('.')[0]):section.p.get_text() for section in soup.select("section")}
    performance = json.loads((OUT/"performance.json").read_text())
    quality = json.loads((OUT/"quality.json").read_text())
    years = json.loads((OUT/"annual_evaluations.json").read_text())
    story = []

    def para(text,style="Text"):
        story.append(Paragraph(safe(text),styles[style]))

    def title(number,text):
        if number > 1:
            story.append(PageBreak())
        para(f"{number:02d} / {text}","Heading")

    def table(frame,widths=None):
        values = [list(frame.columns)]+frame.fillna("Unavailable").astype(str).values.tolist()
        data = [[Paragraph(safe(cell),styles["SmallText"]) for cell in row] for row in values]
        tab = Table(data,colWidths=widths or [WIDTH/len(frame.columns)]*len(frame.columns),repeatRows=1,hAlign="LEFT")
        tab.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#e2e8f0")),
            ("VALIGN",(0,0),(-1,-1),"TOP"),("BOTTOMPADDING",(0,0),(-1,-1),5),
            ("TOPPADDING",(0,0),(-1,-1),5),("LINEBELOW",(0,0),(-1,-1),.3,colors.HexColor("#cbd5e1")),
            ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#f8fafc")])]))
        story.extend([tab,Spacer(1,10)])

    def chart(name,ratio):
        story.append(Image(str(OUT/"figures"/name),width=WIDTH,height=WIDTH*ratio))
        story.append(Spacer(1,8))

    title(1,"Turkish Airlines strategy study")
    para("CSE481 TERM PROJECT | 15 SEPTEMBER 2026","Sub")
    para("Python + Fintables + Model Context Protocol","Sub")
    para(sections[1])
    para("VERIFIED ANNUAL SOURCES - ORIGINAL TRY PRESENTATION","Sub")
    para("Four original Fintables-hosted annual reports supply 136 dated observations, including comparative columns. Publication metadata is verified separately. Later revisions enter only after publication. This is an annual-refresh academic backtest; it does not establish an investable advantage or cover every interim announcement.")
    para(sections[2])
    para("Full-period results at a glance","Sub")
    frame = pd.read_csv(OUT/"performance_table.csv").drop(columns=["Exposure","Sessions"])
    table(frame,[90,80,90,80,75,WIDTH-415])
    para("The combined rule returned more than technical-only trading, with a slightly deeper drawdown. It lagged buy-and-hold and BIST100 while holding a position for about one fifth of sessions. Eight closed trades provide limited evidence. Profitability was never an acceptance criterion.")

    title(2,"Financial evidence and provenance")
    para(sections[4])
    table(pd.read_csv(OUT/"financial_analysis.csv"),[WIDTH*.65,WIDTH*.35])
    para("Source and accounting conventions","Sub")
    para("The user downloaded FY2021-2024 statements from Fintables. PDF pages 9, 10, 11 and 13 were visually reviewed; 40 balance, profit and cash-flow identities reconcile exactly. Millions of TRY are scaled once. FY2020 comparatives become available with the FY2021 release, not retroactively.")
    para("At the final stock date the latest annual accounts are FY2024, released 28 February 2025 and usable from 3 March. Financial values stay in their original TRY presentation: monthly income translation cannot be reversed exactly using one annual exchange rate. Sources, hashes, page references and four dated comparative changes are in docs/ORIGINALS_AUDIT.md.")

    title(3,"Ratios and score interpretation")
    table(pd.read_csv(OUT/"ratio_analysis.csv"),[WIDTH*.6,WIDTH*.4])
    para("Growth and margins are percentages; leverage, liquidity and valuation are multiples. ROE/ROA use average parent equity/total assets. P/E and P/B use raw TRY stock prices and nominal shares against TRY accounts. Negative prior earnings or invalid denominators remain unavailable.")
    para("At 31 December 2025, the fundamental score is 3/5: sales growth, leverage and relative P/E pass. Earnings growth and ROE fail. Technical score is 2/5 and combined score 0.48; the flat-position decision is HOLD because the trend filter fails. The latest annual profit comparison includes FY2023's unusually large deferred-tax gain.")
    chart("scores.png",5/11)

    title(4,"Technical evidence and causal levels")
    para(sections[3])
    chart("technical.png",8/11)
    para("A pivot date and its confirmation date are distinct. The zone table records both, and prefix tests confirm that adding later observations does not rewrite earlier indicators or levels. Support and resistance can switch roles as price moves. Values use adjusted synthetic TRY prices.","SmallText")

    title(5,"Strategy, execution and audit trail")
    para(sections[5])
    para("Example next-open order ledger","Sub")
    orders = pd.read_csv(OUT/"combined_orders.csv")
    columns = ["decision_date","execution_date","side","fill_price","commission","reason"]
    table(orders[columns].head(6).round(3),[76,76,40,70,65,WIDTH-327])
    para("A close-triggered 8% stop executes at the next open, which may gap. The backtest preserves daily cash and units, prohibits repeated entries, accounts for each side's fees and marks remaining positions at the final close. Fractional synthetic adjusted units are an academic approximation; dividends are not added a second time.")
    gross = pd.DataFrame([{"Strategy":name,"Net return %":round(row["cumulative_return"]*100,2),
        "Gross, same executions %":round(row["gross_return_same_executions"]*100,2)} for name,row in performance.items() if name!="bist100"])
    table(gross)
    para("The gross counterfactual holds execution dates and sides fixed and removes fees/slippage. It isolates execution costs more cleanly than re-running the strategy, whose stop dates can change when the entry fill changes.","SmallText")

    title(6,"Results and chronological evaluation")
    para(sections[6])
    chart("performance.png",7/11)
    annual = pd.DataFrame([{"Year":year,"Combined %":round(rows["combined"]["cumulative_return"]*100,2),
        "Technical %":round(rows["technical"]["cumulative_return"]*100,2),"Buy/hold %":round(rows["buy_hold"]["cumulative_return"]*100,2),
        "BIST100 %":round(rows["bist100"]["cumulative_return"]*100,2)} for year,rows in years.items()])
    table(annual)
    para("2023 is development, 2024 validation and 2025 holdout. Each annual evaluation restarts flat with equal capital and uses the preceding feature warm-up; annual returns need not compound to the continuous full-period result.","SmallText")

    title(7,"Sensitivity, verification and limits")
    sensitivity = pd.read_csv(OUT/"sensitivity.csv")
    table(pd.DataFrame({"2023-2024 variant":sensitivity.variant,"Return %":(sensitivity.cumulative_return*100).round(2),
        "Max drawdown %":(sensitivity.maximum_drawdown*100).round(2),"Closed trades":sensitivity.closed_trades}))
    para("Variants were declared before return comparisons; none is selected as a new holdout configuration. A zero-cost rerun can change decisions because the entry fill affects stop thresholds. The fixed-execution counterfactual is reported separately. Source and currency correction occurred after the earlier USD results were inspected.")
    para(sections[9])
    para("Observed data gaps","Sub")
    para(f"Stock evaluation: {quality['evaluation_sessions']} sessions. Complete five-component fundamental score: {quality['fundamental_complete_sessions']} sessions. Missing FX dates: "+", ".join(quality["missing_fx_dates"])+". BIST100 lacks three internal comparison dates; endpoints match. Source prices are not forward-filled.")
    para("Strict source-mode acceptance","Sub")
    para("The original-source gate passes: all 136 observations have source pages, file hashes and verified publication dates. Only reports available at each simulated date enter the strategy. The earlier unverified USD study is retained separately. Its 26.24% combined return is not comparable as a controlled experiment because currency, data versions and dates differ.")

    title(8,"MCP agent and reproduction")
    para(sections[8])
    para("Verified implementation evidence","Sub")
    para("The actual Codex host called the project's history, indicators, zones, fundamentals, scores, signal, backtest and report tools. Its separate missing-data run returned unavailable values and demonstrated INVALID_SYMBOL handling. The stdio integration check compared eight checks with direct Python output. A nine-code-cell walkthrough executed with no cell errors. Full traces and verification records accompany the project.")
    para("Core commands (PowerShell)","Sub")
    for command in [".\\.venv\\Scripts\\python.exe -m bist_analytics.cli import-originals",
                    ".\\.venv\\Scripts\\python.exe -m bist_analytics.cli run",
                    ".\\.venv\\Scripts\\python.exe scripts/sensitivity.py",
                    ".\\.venv\\Scripts\\python.exe scripts/verify_mcp.py"]:
        para(command,"SmallText")
    para("The run manifest pins source files, code hashes, configuration and dependency lock. Offline reproduction requires no financial-site login. New AI runs consume the signed-in host's model usage. Tools are read-only and never place trades. See README.md for the complete setup and refresh procedure.")
    para("Sources and supporting documents","Sub")
    for label,url in [
        ("Fintables THYAO balance sheet","https://fintables.com/sirketler/THYAO/finansal-tablolar/bilanco"),
        ("Fintables THYAO income statement","https://fintables.com/sirketler/THYAO/finansal-tablolar/gelir-tablosu"),
        ("Fintables THYAO cash-flow statement","https://fintables.com/sirketler/THYAO/finansal-tablolar/nakit-akim-tablosu"),
        ("Fintables EBITDA/net-debt definitions","https://fintables.com/arastirma/yazilar/degerleme-analizi-101/fdfavok"),
        ("Yahoo download interface","https://ranaroussi.github.io/yfinance/reference/api/yfinance.download.html"),
        ("Official MCP Python SDK","https://github.com/modelcontextprotocol/python-sdk")]:
        story.append(Paragraph(f'<link href="{url}" color="#2563eb">{safe(label)}</link>',styles["SmallText"]))
    para("Detailed release evidence: docs/DATA_SOURCES.md. Proposal: docs/PROPOSAL.md. Assumptions: docs/DECISIONS.md. Actual AI answer: outputs/agent/analysis_demo.md. Presentation preparation and rehearsal follow implementation, as requested.")
    destination = ROOT/"output/pdf/THYAO_Term_Project_Report.pdf"
    destination.parent.mkdir(parents=True,exist_ok=True)

    def footer(canvas,doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#be123c"))
        canvas.line(44,A4[1]-30,A4[0]-44,A4[1]-30)
        canvas.setFont("Body",7)
        canvas.setFillColor(colors.HexColor("#64748b"))
        canvas.drawString(44,24,"CSE481 | THYAO | Verified annual sources | 15 September 2026")
        canvas.drawRightString(A4[0]-44,24,str(doc.page))
        canvas.restoreState()

    document = SimpleDocTemplate(str(destination),pagesize=A4,leftMargin=44,rightMargin=44,topMargin=47,bottomMargin=44,
        title="THYAO CSE481 Term Project Report",author="CSE481 project",subject="Python/Fintables/MCP study with verified annual sources")
    document.build(story,onFirstPage=footer,onLaterPages=footer)
    print(destination)


if __name__ == "__main__":
    main()
