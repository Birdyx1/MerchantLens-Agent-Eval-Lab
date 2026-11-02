"""真实调用三个 stdio MCP 工具并保存集成验收 Trace。"""

import asyncio
import os
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from mcp import Client, StdioServerParameters

from merchant_agent.tools.sql.init_orders_db import create_orders_db
from merchant_agent.tracing.observed_python import execute_python_observed
from merchant_agent.tracing.observed_search import search_web_observed
from merchant_agent.tracing.observed_sql import call_store_net_observed
from merchant_agent.tracing.reader import read_spans
from merchant_agent.tracing.validator import validate_trace
from merchant_agent.tracing.writer import append_span


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_tavily_key() -> str:
    """读取环境变量或本地配置文件，只解析指定键，不执行文件内容。"""
    key = os.environ.get("TAVILY_API_KEY", "").strip()
    if key:
        return key
    path = PROJECT_ROOT / ".env.tavily"
    if not path.exists():
        raise RuntimeError("缺少 TAVILY_API_KEY 配置")
    for line in path.read_text(encoding="utf-8").splitlines():
        name, separator, value = line.strip().partition("=")
        if separator and name.removeprefix("export ").strip() == "TAVILY_API_KEY":
            value = value.strip().strip("\"'")
            if value:
                return value
    raise RuntimeError("缺少 TAVILY_API_KEY 配置")


async def run_live_smoke() -> tuple[Path, list[str]]:
    """运行真实 stdio、Tavily 与 Docker 调用，返回 Trace 路径和结果类别。"""
    key = _load_tavily_key()
    runs_dir = PROJECT_ROOT / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    trace_path = runs_dir / f"mcp-live-{uuid.uuid4().hex}.jsonl"
    trace_id = uuid.uuid4().hex
    parent_span_id = uuid.uuid4().hex[:16]
    started_at = datetime.now(timezone.utc).isoformat()

    with tempfile.TemporaryDirectory() as directory:
        db_path = Path(directory) / "orders.sqlite"
        create_orders_db(str(PROJECT_ROOT / "fixtures/business_data/orders.csv"), str(db_path))
        env = {
            "MERCHANT_DB_PATH": str(db_path),
            "MERCHANT_ENABLE_PYTHON": "1",
            "MERCHANT_SANDBOX_JOURNAL": str(runs_dir / "python_sandbox.sqlite3"),
            "TAVILY_API_KEY": key,
            "PYTHONPATH": str(PROJECT_ROOT / "src"),
            "PATH": os.environ.get("PATH", ""),
            "HOME": os.environ.get("HOME", ""),
        }
        server = StdioServerParameters(
            command=sys.executable, args=["-m", "merchant_agent.mcp_stdio"], env=env
        )
        async with Client(server) as client:
            names = {tool.name for tool in (await client.list_tools()).tools}
            if names != {"get_store_net", "search_web", "execute_python"}:
                raise RuntimeError("MCP 三工具发现结果不符合预期")
            amount = await call_store_net_observed(
                client, "A", trace_path=str(trace_path), trace_id=trace_id,
                parent_span_id=parent_span_id, operation_id="sql-1"
            )
            snapshot = await search_web_observed(
                client, "Example Domain", 1, trace_path=str(trace_path), trace_id=trace_id,
                parent_span_id=parent_span_id, operation_id="search-1"
            )
            python_result = await execute_python_observed(
                client, 'print("sandbox-ready")', 2, trace_path=str(trace_path),
                trace_id=trace_id, parent_span_id=parent_span_id, operation_id="python-1"
            )
    append_span(str(trace_path), {
        "trace_id": trace_id,
        "span_id": parent_span_id,
        "parent_span_id": None,
        "name": "agent.request",
        "start_time": started_at,
        "end_time": datetime.now(timezone.utc).isoformat(),
        "attributes": {"purpose": "mcp_live_smoke"},
    })
    if amount != 12000 or not isinstance(snapshot["results"], list):
        raise RuntimeError("SQL 或搜索结果不符合预期")
    if python_result.status != "succeeded" or python_result.stdout.strip() != "sandbox-ready":
        raise RuntimeError("Python 容器执行结果不符合预期")
    spans = read_spans(str(trace_path))
    if (len(spans) != 4 or validate_trace(spans)
            or any(span["parent_span_id"] != parent_span_id for span in spans[:3])
            or spans[3]["span_id"] != parent_span_id):
        raise RuntimeError("工具 Trace 记录不完整")
    return trace_path, [span["attributes"]["outcome"] for span in spans[:3]]


if __name__ == "__main__":
    path, outcomes = asyncio.run(run_live_smoke())
    print(f"Trace: {path}")
    print(f"工具结果类别: {outcomes}")
