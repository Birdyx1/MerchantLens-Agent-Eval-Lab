import asyncio
import sqlite3

from mcp import Client

from merchant_agent.agent.planning import valid_tool_arguments
from merchant_agent.mcp_server import create_server
from merchant_agent.tracing.observed_sql import call_run_sql_observed
from merchant_agent.tracing.reader import read_spans


TRACE_ID = "a" * 32
PARENT_ID = "b" * 16


def test_valid_tool_arguments_accepts_run_sql():
    assert valid_tool_arguments("run_sql", {"query": "SELECT 1"}) is True
    assert valid_tool_arguments("run_sql", {"query": ""}) is False
    assert valid_tool_arguments("run_sql", {"query": "  "}) is False
    assert valid_tool_arguments("run_sql", {"query": "SELECT 1", "db": "x"}) is False


def test_call_run_sql_observed_records_result_set(tmp_path):
    db = tmp_path / "o.sqlite"
    with sqlite3.connect(db) as connection:
        connection.execute(
            "CREATE TABLE orders (order_id TEXT, store_id TEXT, paid_fen INTEGER, refunded_fen INTEGER)"
        )
        connection.execute("INSERT INTO orders VALUES ('1', 'A', 100, 0)")
    trace_path = tmp_path / "trace.jsonl"

    async def run():
        async with Client(create_server(str(db))) as client:
            return await call_run_sql_observed(
                client, "SELECT COUNT(*) AS c FROM orders",
                trace_path=str(trace_path), trace_id=TRACE_ID,
                parent_span_id=PARENT_ID, operation_id="op-1",
            )

    result = asyncio.run(run())
    assert result["outcome"] == "success"
    assert result["rows"] == [[1]]
    spans = read_spans(str(trace_path))
    assert spans[0]["name"] == "tool.run_sql"
    assert spans[0]["attributes"]["result_set"]["rows"] == [[1]]
    assert spans[0]["attributes"]["query"] == "SELECT COUNT(*) AS c FROM orders"


def test_call_run_sql_observed_records_security_rejection(tmp_path):
    db = tmp_path / "o.sqlite"
    with sqlite3.connect(db) as connection:
        connection.execute(
            "CREATE TABLE orders (order_id TEXT, store_id TEXT, paid_fen INTEGER, refunded_fen INTEGER)"
        )
    trace_path = tmp_path / "trace.jsonl"

    async def run():
        async with Client(create_server(str(db))) as client:
            return await call_run_sql_observed(
                client, "DROP TABLE orders",
                trace_path=str(trace_path), trace_id=TRACE_ID,
                parent_span_id=PARENT_ID, operation_id="op-2",
            )

    result = asyncio.run(run())
    assert result["outcome"] == "security_rejected"
    spans = read_spans(str(trace_path))
    assert spans[0]["attributes"]["outcome"] == "security_rejected"
