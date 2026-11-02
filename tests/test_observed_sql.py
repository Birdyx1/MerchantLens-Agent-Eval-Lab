import asyncio
import sqlite3
from types import SimpleNamespace

import pytest
from mcp import Client

from merchant_agent.mcp_server import create_server
from merchant_agent.tracing.observed_sql import call_store_net_observed
from merchant_agent.tracing.reader import read_spans


TRACE_ID = "a" * 32
PARENT_ID = "b" * 16


def _call(client, trace_path, store_id="A", attempt=1, operation_id="op-1"):
    return call_store_net_observed(
        client, store_id, trace_path=str(trace_path), trace_id=TRACE_ID,
        parent_span_id=PARENT_ID, operation_id=operation_id, attempt=attempt,
    )


def test_real_mcp_sql_success_and_empty_result(tmp_path):
    db_path = tmp_path / "orders.sqlite"
    with sqlite3.connect(db_path) as db:
        db.execute("CREATE TABLE orders (order_id TEXT, store_id TEXT, paid_fen INTEGER, refunded_fen INTEGER)")
        db.execute("INSERT INTO orders VALUES ('1', 'A', 15000, 3000)")
    trace_path = tmp_path / "trace.jsonl"

    async def run():
        async with Client(create_server(str(db_path))) as client:
            assert await _call(client, trace_path, "A", 1) == 12000
            assert await _call(client, trace_path, "unknown", operation_id="op-2") is None

    asyncio.run(run())
    first, second = read_spans(str(trace_path))
    assert first["span_id"] != second["span_id"]
    assert first["trace_id"] == second["trace_id"] == TRACE_ID
    assert first["parent_span_id"] == second["parent_span_id"] == PARENT_ID
    assert [first["attributes"]["operation_id"], second["attributes"]["operation_id"]] == ["op-1", "op-2"]
    assert [first["attributes"]["attempt"], second["attributes"]["attempt"]] == [1, 1]
    assert first["attributes"]["outcome"] == "success"
    assert first["attributes"]["result_fen"] == 12000
    assert second["attributes"]["outcome"] == "empty_result"
    assert second["attributes"]["result_fen"] is None


class FakeClient:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = 0

    async def call_tool(self, name, arguments):
        self.calls += 1
        if self.error:
            raise self.error
        return self.response


@pytest.mark.parametrize("client, outcome, raw_status", [
    (FakeClient(SimpleNamespace(is_error=True, structured_content=None)), "dependency_error", "mcp_error"),
    (FakeClient(SimpleNamespace(is_error=False, structured_content={})), "dependency_error", "protocol_error"),
    (FakeClient(error=asyncio.TimeoutError()), "timeout", "timeout"),
])
def test_failure_is_recorded_and_propagated(tmp_path, client, outcome, raw_status):
    trace_path = tmp_path / "trace.jsonl"
    with pytest.raises((RuntimeError, asyncio.TimeoutError)):
        asyncio.run(_call(client, trace_path))
    spans = read_spans(str(trace_path))
    assert len(spans) == 1
    assert spans[0]["attributes"]["outcome"] == outcome
    assert spans[0]["attributes"]["raw_status"] == raw_status
    assert "error_type" in spans[0]["attributes"]


def test_invalid_attempt_rejected_before_call(tmp_path):
    client = FakeClient()
    with pytest.raises(ValueError):
        asyncio.run(_call(client, tmp_path / "trace.jsonl", attempt=0))
    assert client.calls == 0
    assert not (tmp_path / "trace.jsonl").exists()


def test_two_attempts_keep_failure_and_success(tmp_path):
    class FlakyClient:
        def __init__(self):
            self.calls = 0

        async def call_tool(self, name, arguments):
            self.calls += 1
            if self.calls == 1:
                raise asyncio.TimeoutError()
            return SimpleNamespace(is_error=False, structured_content={"result": 12000})

    client = FlakyClient()
    trace_path = tmp_path / "trace.jsonl"

    async def run():
        with pytest.raises(asyncio.TimeoutError):
            await _call(client, trace_path, attempt=1)
        assert await _call(client, trace_path, attempt=2) == 12000

    asyncio.run(run())
    first, second = read_spans(str(trace_path))
    assert first["span_id"] != second["span_id"]
    assert first["attributes"]["operation_id"] == second["attributes"]["operation_id"]
    assert [first["attributes"]["attempt"], second["attributes"]["attempt"]] == [1, 2]
    assert [first["attributes"]["outcome"], second["attributes"]["outcome"]] == ["timeout", "success"]
