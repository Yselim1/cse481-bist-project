"""Create and execute a self-contained offline walkthrough in this interpreter."""

import json
import os
import sys
from pathlib import Path

import nbformat as nb
from jupyter_client import KernelManager
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[1]


def main():
    cells = []

    def markdown(text):
        cells.append(nb.v4.new_markdown_cell(text))

    def code(text):
        cells.append(nb.v4.new_code_cell(text))

    markdown("# Turkish Airlines: reproducible CSE481 walkthrough\n\n"
        "Research question: how does an annual Fintables fundamental filter change a technical strategy?\n\n"
        "**Verified annual source study:** original Fintables-hosted reports, original TRY presentation and verified publication dates. "
        "Comparative revisions enter when published. This does not establish an investable advantage. All financial values are from Fintables.")
    code("from pathlib import Path\nimport json\nimport pandas as pd\nfrom IPython.display import display, Image\n"
         "from bist_analytics.config import project_root, load_config\nfrom bist_analytics.pipeline import run_pipeline\n"
         "from bist_analytics.data.fundamentals import load_observations, quality_report\n"
         "ROOT = project_root()\ncfg = load_config()\nprint('Python project:', ROOT)\nprint('Mode:', cfg.vintage_policy)")
    markdown("## 1. Source inventory and units\n\nAnnual flow totals differ from instant balances. "
             "Millions in the original statements become full TRY amounts exactly once. "
             "TRY paid-in capital supplies nominal share units. Sources and timing evidence are in `docs/DATA_SOURCES.md`.")
    code("records = load_observations(ROOT/cfg.fundamentals_file)\n"
         "display(pd.DataFrame([quality_report(records)]))\n"
         "display(records[['metric','period_end','period_type','value','currency','published_at','assumed_published_at','vintage_verified']].head(10))")
    markdown("## 2. Reproduce the complete pipeline offline\n\nThis cell rebuilds all metrics and report artifacts using saved, hashed sources.")
    code("run = run_pipeline(ROOT, cfg)\nOUT = Path(run['output'])\n"
         "features = pd.read_parquet(OUT/'features.parquet')\n"
         "display(pd.DataFrame(run['quality']['market']).T)\nprint('Missing FX dates:', run['quality']['missing_fx_dates'])")
    markdown("## 3. Causal technical evidence\n\nEMA uses a simple-average seed; RSI uses Wilder smoothing. "
             "Pivots are usable only after five confirming sessions. The plotted levels are the levels known at each close.")
    code("display(features[['close','sma_fast','sma_slow','ema_fast','rsi','macd','macd_signal','relative_volume','support','resistance']].tail())\n"
         "display(Image(filename=str(OUT/'figures/technical.png')))")
    markdown("## 4. Financial alignment and explainable scoring\n\nBackward joins use the first stock session after a verified or assumed release date. "
             "No initial backfill is used. The original-report archive preserves current and comparative columns as separately dated observations.")
    code("snapshots = pd.read_csv(OUT/'financial_snapshots.csv')\n"
         "display(snapshots[['financial_period','available_at','revenue','net_profit','ebitda','roe','net_debt_ebitda']])\n"
         "columns = [c for c in features if c.startswith(('t_','f_'))] + ['technical_score','fundamental_score','combined_score']\n"
         "display(features[columns].tail(1).T)\ndisplay(Image(filename=str(OUT/'figures/scores.png')))")
    markdown("## 5. Decisions, next-open orders and costs\n\nA close-triggered stop does not guarantee the stop price. "
             "The following order ledger shows actual simulated dates, fills, slippage and fees; no real order is sent.")
    code("orders = pd.read_csv(OUT/'combined_orders.csv', parse_dates=['decision_date','execution_date'])\n"
         "assert (orders.execution_date > orders.decision_date).all()\ndisplay(orders.head(8))\n"
         "display(pd.read_csv(OUT/'combined_trades.csv'))")
    markdown("## 6. Results and baselines\n\nReturns are nominal TRY and cash earns zero. "
             "BIST100 is a price index with three missing comparison sessions; the adjusted stock series uses synthetic fractional units. "
             "Win rate only counts closed trades, so buy-and-hold has no closed-trade win rate.")
    code("display(pd.read_csv(OUT/'performance_table.csv'))\n"
         "display(Image(filename=str(OUT/'figures/performance.png')))\n"
         "annual = json.loads((OUT/'annual_evaluations.json').read_text())\n"
         "display(pd.DataFrame({year:{mode:m['cumulative_return'] for mode,m in data.items()} for year,data in annual.items()}).T)")
    markdown("## 7. Predeclared sensitivity and strict source mode\n\n2023–2024 variants do not select a winner on the 2025 holdout. "
             "A zero-cost rerun can change stop timing; the separate gross counterfactual keeps execution dates fixed. "
             "Strict source mode now admits the 136 reviewed original-report observations. The earlier USD table study remains separately qualified.")
    code("from scripts.sensitivity import main as run_sensitivity\nrun_sensitivity()\n"
         "display(pd.read_csv(OUT/'sensitivity.csv')[['variant','cumulative_return','maximum_drawdown','closed_trades']])\n"
         "from bist_analytics.analysis.fundamentals import get_fundamental_metrics\n"
         "strict = get_fundamental_metrics(records, '2025-12-31', currency=cfg.fundamental_currency)\nassert strict['revenue'] == 745430000000\n"
         "print('Strict source result:', strict['financial_status'])")
    markdown("## 8. Genuine MCP AI evidence\n\nThe following trace was produced by an actual authenticated LLM host, not a mocked conversation. "
             "Re-reading it is offline. A fresh model run is optional because it consumes model usage.")
    code("trace = ROOT/'outputs/agent/analysis_demo.jsonl'\n"
         "events = [json.loads(line) for line in trace.read_text(encoding='utf-8').splitlines()]\n"
         "calls = [e['item'] for e in events if e.get('type')=='item.completed' and e.get('item',{}).get('type')=='mcp_tool_call']\n"
         "display(pd.DataFrame([{'tool':c['tool'],'status':c['status'],'error':c.get('error')} for c in calls]))\n"
         "print((ROOT/'outputs/agent/analysis_demo.md').read_text(encoding='utf-8'))")
    markdown("## 9. Interpretation and acceptance boundary\n\n"
        "The combined rule exceeded technical-only endpoint return but underperformed stock buy-and-hold and BIST100. "
        "Eight closed trades are weak evidence for generalization. Annual updates, nominal currency translation, "
        "one selected stock, inflation, simplistic execution and benchmark differences limit the conclusions. "
        "The source correction followed inspection of the earlier USD run, so the chronological holdout is not a pristine blind test. See the report, source manifest and acceptance audit; "
        "presentation preparation follows implementation.")
    notebook = nb.v4.new_notebook(cells=cells,metadata={"kernelspec":{"display_name":"Python 3 (project environment)","language":"python","name":"python3"},
        "language_info":{"name":"python","version":sys.version.split()[0]}})
    directory = ROOT/"notebooks"
    directory.mkdir(exist_ok=True)
    temporary = ROOT/"tmp/notebook"
    temporary.mkdir(parents=True,exist_ok=True)
    os.environ["IPYTHONDIR"] = str(ROOT/".cache/ipython")
    os.environ["JUPYTER_RUNTIME_DIR"] = str(temporary)
    manager = KernelManager(kernel_name="python3",connection_file=str(temporary/"kernel.json"))
    manager.kernel_spec.argv = [sys.executable,"-m","ipykernel_launcher","-f","{connection_file}"]
    client = NotebookClient(notebook,km=manager,timeout=180,resources={"metadata":{"path":str(ROOT)}})
    client.execute(cleanup_kc=True)
    path = directory/"THYAO_walkthrough.ipynb"
    nb.write(notebook,path)
    errors = [out for cell in notebook.cells if cell.cell_type=="code" for out in cell.outputs if out.output_type=="error"]
    assert not errors
    proof = {"notebook":str(path.relative_to(ROOT)),"code_cells":sum(c.cell_type=="code" for c in cells),
             "errors":len(errors),"python":sys.version,"executed":True}
    (ROOT/"outputs/verification").mkdir(parents=True,exist_ok=True)
    (ROOT/"outputs/verification/notebook.json").write_text(json.dumps(proof,indent=2),encoding="utf-8")
    print(json.dumps(proof))


if __name__ == "__main__":
    main()
