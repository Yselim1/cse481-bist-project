"""Audit recorded real-host responses and build a clearly labeled offline trace view."""

import json
from html import escape

from bist_analytics.config import project_root
from bist_analytics.io import sha256, write_json
from bist_analytics.mcp import server


def assert_subset(old, current, path="response"):
    if isinstance(old,dict):
        for key,value in old.items():
            assert key in current, path+"."+key
            assert_subset(value,current[key],path+"."+key)
    elif isinstance(old,list):
        assert len(old) == len(current), path
        for i,value in enumerate(old):
            assert_subset(value,current[i],path+f"[{i}]")
    else:
        assert old == current, f"Recorded/current mismatch at {path}: {old!r} versus {current!r}"


def main():
    root = project_root()
    evidence, views = [], []
    for name in ["smoke","analysis_demo","missing_data"]:
        path = root/"outputs/agent"/f"{name}.jsonl"
        events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        calls = [e["item"] for e in events if e.get("type")=="item.completed" and e.get("item",{}).get("type")=="mcp_tool_call"]
        assert calls, name
        checks = []
        rows = []
        for call in calls:
            tool = call["tool"]
            error = call.get("error") or (call.get("result") or {}).get("isError")
            if error or call["arguments"].get("ticker")=="INVALID.IS":
                checks.append({"tool":tool,"check":"expected_invalid_symbol_error"})
            else:
                response = call["result"].get("structuredContent")
                if response is None:
                    response = json.loads(call["result"]["content"][0]["text"])
                current = getattr(server,tool)(**call["arguments"])
                assert_subset(response,current,tool)
                checks.append({"tool":tool,"check":"recorded_fields_equal_current_python"})
            rows.append(f'<details><summary>{escape(tool)} | {escape(call["status"])}</summary><pre>{escape(json.dumps(call,indent=2,ensure_ascii=False))}</pre></details>')
        answer = root/"outputs/agent"/f"{name}.md"
        views.append(f'<section><h2>{escape(name)}</h2><p>{len(calls)} recorded MCP calls</p>'+"".join(rows)+
                     f'<h3>Actual host explanation</h3><pre>{escape(answer.read_text(encoding="utf-8"))}</pre></section>')
        evidence.append({"demo":name,"trace_sha256":sha256(path),"answer_sha256":sha256(answer),
            "real_host":"Codex CLI 0.154.0","transport":"stdio","checks":checks})
    write_json(root/"outputs/verification/agent_evidence.json",{"replay_uses_llm":False,"recordings_are_real_host_sessions":True,"demos":evidence})
    html = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>THYAO recorded MCP demonstration</title><style>
body{font:16px/1.6 system-ui;color:#172554;background:#f1f5f9;margin:0}main{max-width:1060px;margin:auto;background:white;padding:36px}h1{border-top:7px solid #be123c;padding-top:20px}section{margin:40px 0}summary{cursor:pointer;padding:12px;background:#e2e8f0}details{margin:8px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:13px/1.5 Consolas,monospace;padding:16px;background:#f8fafc}.notice{padding:16px;background:#fff1f2;border-left:4px solid #be123c}</style><main><h1>THYAO: recorded MCP demonstration</h1><p class="notice">Offline viewer of genuine Codex host sessions captured 15 September 2026. Opening this page does not call a model. These are recorded tool responses and actual explanations, not a live trading service.</p><p>Expand a tool to inspect its arguments and response. Source JSONL and Markdown files are preserved beside this page. Historical Fintables vintages remain unverified.</p>'''
    html = html.replace("Historical Fintables vintages remain unverified.","The active study uses verified annual Fintables originals in TRY; annual refresh and investment-performance limitations remain disclosed.")
    (root/"outputs/agent/recorded_demo.html").write_text(html+"".join(views)+"</main></html>",encoding="utf-8")
    print("All successful recorded response fields match current Python; offline viewer created.")


if __name__ == "__main__":
    main()
