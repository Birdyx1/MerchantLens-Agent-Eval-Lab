"""通过标准输入输出启动本地商家工具 MCP 服务。"""

import os

from merchant_agent.mcp_server import create_server
from merchant_agent.tools.python_sandbox.python_runner import run_python
from merchant_agent.tools.search.tavily_provider import TavilySearchProvider


def main() -> None:
    db_path = os.environ.get("MERCHANT_DB_PATH", "").strip()
    if not db_path:
        raise RuntimeError("缺少 MERCHANT_DB_PATH 环境变量")

    python_enabled = os.environ.get("MERCHANT_ENABLE_PYTHON", "0")
    if python_enabled not in {"0", "1"}:
        raise ValueError("MERCHANT_ENABLE_PYTHON 只能为 0 或 1")

    search_provider = TavilySearchProvider() if os.environ.get("TAVILY_API_KEY", "").strip() else None
    python_executor = run_python if python_enabled == "1" else None
    server = create_server(db_path, search_provider=search_provider, python_executor=python_executor)
    server.run()


if __name__ == "__main__":
    main()
