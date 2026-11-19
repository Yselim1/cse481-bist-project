"""Real stdio protocol checks, separately labeled from the LLM demonstration."""

import asyncio
import json
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from bist_analytics.config import project_root
from bist_analytics.io import write_json
from bist_analytics.mcp import server as direct


async def main():
    params = StdioServerParameters(command=sys.executable,args=["-m","bist_analytics.mcp.server"],cwd=str(project_root()))
    checks = []
    async with stdio_client(params) as (reader,writer):
        async with ClientSession(reader,writer) as session:
            await session.initialize()
            listing = await session.list_tools()
            # Phase D expands the catalogue from 9 → 19. The originals must still be present
            # and every exposed tool must remain read-only/closed-world.
            tool_names = {tool.name for tool in listing.tools}
            original_nine = {"project_status", "get_context_events", "get_stock_history",
                              "calculate_indicators", "find_support_resistance",
                              "get_fundamental_metrics", "calculate_scores",
                              "run_backtest", "generate_signal", "generate_report"}
            assert original_nine.issubset(tool_names), (
                f"original tools missing from catalogue: {original_nine - tool_names}")
            assert len(listing.tools) >= 19, f"expected ≥19 tools, got {len(listing.tools)}"
            for tool in listing.tools:
                assert tool.annotations.read_only_hint is True
            for name,args in [("project_status",{}),("calculate_indicators",{}),("get_fundamental_metrics",{}),
                              ("calculate_scores",{}),("generate_signal",{}),("run_backtest",{})]:
                response = await session.call_tool(name,args)
                assert not response.is_error
                body = response.structured_content
                if body is None:
                    body = json.loads(response.content[0].text)
                expected = getattr(direct,name)(**args)
                assert body == expected, f"MCP versus direct Python mismatch: {name}"
                checks.append({"tool":name,"result":"equal_to_direct_python"})
            bad = await session.call_tool("get_stock_history",{"ticker":"INVALID.IS"})
            assert bad.is_error
            checks.append({"tool":"get_stock_history","result":"invalid_symbol_rejected"})
            early = await session.call_tool("get_fundamental_metrics",{"as_of":"2021-01-15"})
            body = early.structured_content or json.loads(early.content[0].text)
            assert body["data"]["revenue"] is None
            checks.append({"tool":"get_fundamental_metrics","result":"missing_data_returned_as_null"})
    write_json(project_root()/"outputs/verification/mcp_protocol.json",{"transport":"stdio","real_llm":False,"checks":checks})
    print(f"MCP protocol: {len(checks)} checks passed")


if __name__ == "__main__":
    asyncio.run(main())
