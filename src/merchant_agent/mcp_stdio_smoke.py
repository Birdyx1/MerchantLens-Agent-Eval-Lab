"""通过真实的标准输入输出子进程验证本地 MCP 服务。"""

import sys
from pathlib import Path

from mcp import Client, StdioServerParameters


async def discover_stdio_tools(
    db_path: str, *, enable_search: bool = False, enable_python: bool = False
) -> set[str]:
    """在真实子进程中发现工具，不调用外部服务。"""
    env = {"MERCHANT_DB_PATH": db_path, "PYTHONPATH": str(Path(__file__).resolve().parents[1]),
           "MERCHANT_ENABLE_PYTHON": "1" if enable_python else "0"}
    if enable_search:
        # 仅用于工具发现；不会用这个标记值请求 Tavily。
        env["TAVILY_API_KEY"] = "discovery-only"
    server = StdioServerParameters(command=sys.executable, args=["-m", "merchant_agent.mcp_stdio"], env=env)
    async with Client(server) as client:
        return {tool.name for tool in (await client.list_tools()).tools}


async def smoke_stdio(db_path: str) -> int | None:
    src_path = Path(__file__).resolve().parents[1]
    server = StdioServerParameters(
        command=sys.executable,
        args=["-m", "merchant_agent.mcp_stdio"],
        env={"MERCHANT_DB_PATH": db_path, "PYTHONPATH": str(src_path),
             "MERCHANT_ENABLE_PYTHON": "0"},
    )

    async with Client(server) as client:
        tools = await client.list_tools()
        if not any(tool.name == "get_store_net" for tool in tools.tools):
            raise RuntimeError("MCP 服务未暴露 get_store_net")

        result = await client.call_tool("get_store_net", {"store_id": "A"})
        if result.is_error:
            raise RuntimeError("get_store_net 工具调用失败")
        if result.structured_content is None or "result" not in result.structured_content:
            raise RuntimeError("get_store_net 缺少结构化结果")
        return result.structured_content["result"]
