import asyncio
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft202012Validator
from mcp import Client

from merchant_agent.mcp_server import create_server
from merchant_agent.tools.python_sandbox.python_result import PythonRunResult
from merchant_agent.tools.search.fake_search import FakeSearchProvider
from merchant_agent.tools.search.search_result import SearchResult
from merchant_agent.tracing.observed_python import execute_python_observed
from merchant_agent.tracing.observed_search import search_web_observed
from merchant_agent.tracing.observed_sql import call_store_net_observed
from merchant_agent.tracing.reader import read_spans
from merchant_agent.tracing.validator import validate_trace
from merchant_agent.tracing.writer import append_span


def test_three_tools_share_one_valid_trace(tmp_path):
    db_path = tmp_path / "orders.sqlite"
    with sqlite3.connect(db_path) as db:
        db.execute("CREATE TABLE orders (order_id TEXT, store_id TEXT, paid_fen INTEGER, refunded_fen INTEGER)")
        db.execute("INSERT INTO orders VALUES ('1', 'A', 15000, 3000)")

    search = FakeSearchProvider([
        SearchResult("商家指南", "https://example.com/guide", "商家经营建议",
                     "2026-11-01T00:00:00Z", "fake")
    ])
    python_result = PythonRunResult("succeeded", "12000\n", "", 0, 9, False, False, False)
    server = create_server(str(db_path), search_provider=search,
                           python_executor=lambda code, timeout: python_result)
    trace_id, parent_id = "a" * 32, "b" * 16
    trace_path = tmp_path / "trace.jsonl"
    started_at = datetime.now(timezone.utc).isoformat()

    async def run():
        async with Client(server) as client:
            assert await call_store_net_observed(
                client, "A", trace_path=str(trace_path), trace_id=trace_id,
                parent_span_id=parent_id, operation_id="sql-1") == 12000
            snapshot = await search_web_observed(
                client, "商家", 2, trace_path=str(trace_path), trace_id=trace_id,
                parent_span_id=parent_id, operation_id="search-1")
            assert len(snapshot["results"]) == 1
            result = await execute_python_observed(
                client, "print(12000)", 2, trace_path=str(trace_path), trace_id=trace_id,
                parent_span_id=parent_id, operation_id="python-1")
            assert result == python_result

    asyncio.run(run())
    append_span(str(trace_path), {
        "trace_id": trace_id, "span_id": parent_id, "parent_span_id": None,
        "name": "agent.request", "start_time": started_at,
        "end_time": datetime.now(timezone.utc).isoformat(), "attributes": {},
    })

    spans = read_spans(str(trace_path))
    schema_path = Path(__file__).resolve().parents[1] / "schemas" / "span.schema.json"
    validator = Draft202012Validator(json.loads(schema_path.read_text(encoding="utf-8")))
    assert len(spans) == 4
    assert all(validator.is_valid(span) for span in spans)
    assert validate_trace(spans) == []
    assert {span["name"] for span in spans} == {
        "tool.get_store_net", "tool.search_web", "tool.execute_python", "agent.request"
    }
    assert all(span["parent_span_id"] == parent_id for span in spans[:3])
    assert len({span["attributes"]["operation_id"] for span in spans[:3]}) == 3
    assert [span["attributes"]["outcome"] for span in spans[:3]] == ["success"] * 3
    assert spans[1]["attributes"]["search_snapshot"]["results"][0]["url"] == "https://example.com/guide"
    assert spans[2]["attributes"]["python_result"]["stdout"] == "12000\n"
