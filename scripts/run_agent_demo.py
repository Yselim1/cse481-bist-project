"""Exercise an actual LLM host against this project's stdio MCP server.

Uses existing Codex authentication. Never modifies global MCP settings or reads credentials.
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--missing", action="store_true")
    args = parser.parse_args()
    codex = shutil.which("codex") or str(Path.home()/"AppData/Local/Programs/OpenAI/Codex/bin/codex.exe")
    if not Path(codex).exists():
        raise SystemExit("Install the official Codex CLI and sign in, or configure another MCP-capable host.")
    folder = ROOT/"outputs/agent"
    folder.mkdir(parents=True,exist_ok=True)
    name = "smoke" if args.smoke else "missing_data" if args.missing else "analysis_demo"
    prompt = ("Call the bist project_status MCP tool exactly once. Report its ticker and fundamental source. "
              "Use no shell tools and make no file changes.") if args.smoke else (
        "Use only the bist MCP tools; do not use shell tools, web browsing or edit files. "
        "This is an academic financial-analysis agent demonstration. "
        + ("Analyze THYAO.IS as of 2021-01-15: call get_fundamental_metrics, calculate_scores and generate_signal. "
           "Explain missing historical fundamentals without inventing any financial figure. Also call get_stock_history "
           "with INVALID.IS to demonstrate the bounded invalid-symbol error. " if args.missing else
           "Analyze THYAO.IS as of 2025-12-31. Call get_stock_history, calculate_indicators, find_support_resistance, "
           "get_fundamental_metrics, calculate_scores, generate_signal with holding=false, and run_backtest "
           "for 2023-01-01 to exclusive 2026-01-01. Also call generate_report. Give a concise academic explanation "
           "of the technical/fundamental evidence and current rule signal, then a small table of strategy and baseline "
           "returns, max drawdown, zero-risk-free Sharpe and closed-trade win rate. ")
        + "All financial numbers must come from the tools. State actual market/financial dates, active currency units, "
          "costs and historical vintage/release policy. Distinguish verified annual source vintages from investment performance validation; "
          "do not claim an investable advantage. "
          "Cite tool names and local report path. Missing values are unavailable, not zero. No outside calculations."
    )
    command = [codex,"exec","--ignore-user-config","--ephemeral","--json","--sandbox","read-only",
        "-C",str(ROOT),"-c",'mcp_servers.bist.command='+json.dumps(sys.executable.replace("\\","/")),
        "-c",'mcp_servers.bist.args=["-m","bist_analytics.mcp.server"]',
        "-c","mcp_servers.bist.required=true","-c","mcp_servers.bist.startup_timeout_sec=45",
        "-c","mcp_servers.bist.tool_timeout_sec=120","-o",str(folder/f"{name}.md"),prompt]
    with (folder/f"{name}.jsonl").open("w",encoding="utf-8") as stdout, (folder/f"{name}.stderr.log").open("w",encoding="utf-8") as stderr:
        process = subprocess.run(command,stdout=stdout,stderr=stderr,cwd=ROOT,timeout=600)
    events = [json.loads(line) for line in (folder/f"{name}.jsonl").read_text(encoding="utf-8").splitlines() if line.strip().startswith("{")]
    calls = [event["item"] for event in events if event.get("type") == "item.completed" and event.get("item",{}).get("type") == "mcp_tool_call"]
    successful = {call["tool"] for call in calls if call.get("status") == "completed" and not call.get("error")}
    expected = {"project_status"} if args.smoke else {"get_fundamental_metrics","calculate_scores","generate_signal"} if args.missing else {"get_stock_history","calculate_indicators","find_support_resistance","get_fundamental_metrics","calculate_scores","generate_signal","run_backtest","generate_report"}
    if process.returncode == 0 and not expected <= successful:
        raise SystemExit("Host finished without required successful MCP calls. Inspect the trace; this is not a passed demo.")
    print(json.dumps({"exit_code":process.returncode,"trace":str(folder/f"{name}.jsonl"),
                      "answer":str(folder/f"{name}.md")}))
    raise SystemExit(process.returncode)


if __name__ == "__main__":
    main()
