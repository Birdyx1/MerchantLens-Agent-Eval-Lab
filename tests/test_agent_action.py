import asyncio
import json
import sqlite3
from types import SimpleNamespace

import pytest
from mcp import Client

from merchant_agent.agent.action import make_tool_node
from merchant_agent.agent.graph import build_single_turn_graph
from merchant_agent.agent.model_port import ModelResponse
from merchant_agent.agent.state import initial_state
from merchant_agent.mcp_server import create_server
from merchant_agent.tools.python_sandbox.python_result import PythonRunResult
from merchant_agent.tools.search.fake_search import FakeSearchProvider
from merchant_agent.tools.search.search_result import SearchResult
from merchant_agent.tracing.reader import read_spans
from merchant_agent.tracing import observed_sql


class FixedModel:
    def __init__(self, tool_name, arguments):
        self.text = json.dumps({
            "plan": ["调用业务工具"],
            "action": {"type": "tool", "name": tool_name, "arguments": arguments},
        })

    async def generate(self, messages):
        return ModelResponse(self.text, "fixed-model", 8, 3)


@pytest.mark.parametrize("tool_name, arguments, expected_outcome", [
    ("get_store_net", {"store_id": "A"}, "success"),
    ("search_web", {"query": "商家", "limit": 1}, "success"),
    ("execute_python", {"code": "print(1)", "timeout_seconds": 2}, "program_error"),
])
def test_graph_action_uses_real_mcp_protocol(tmp_path, tool_name, arguments, expected_outcome):
    db_path = tmp_path / "orders.sqlite"
    with sqlite3.connect(db_path) as db:
        db.execute("CREATE TABLE orders (order_id TEXT, store_id TEXT, paid_fen INTEGER, refunded_fen INTEGER)")
        db.execute("INSERT INTO orders VALUES ('1', 'A', 15000, 3000)")
    search = FakeSearchProvider([
        SearchResult("商家指南", "https://example.com/guide", "商家经营建议",
                     "2026-11-02T00:00:00Z", "fake")
    ])
    python_result = PythonRunResult("program_error", "", "ZeroDivisionError", 1, 10,
                                    False, False, False)
    server = create_server(str(db_path), search_provider=search,
                           python_executor=lambda code, timeout: python_result)
    trace_path = tmp_path / "trace.jsonl"

    async def run():
        async with Client(server) as client:
            graph = build_single_turn_graph(FixedModel(tool_name, arguments),
                                            make_tool_node(client, str(trace_path)))
            return await graph.ainvoke(initial_state("task-1", "a" * 32, "b" * 16, "分析门店 A"))

    state = asyncio.run(run())
    (span,) = read_spans(str(trace_path))
    observation = state["last_tool_result"]
    assert state["selected_tool"] == tool_name
    assert state["tool_attempt"] == 1
    assert state["operation_id"] == span["attributes"]["operation_id"]
    assert state["step_count"] == 2
    assert observation["outcome"] == span["attributes"]["outcome"] == expected_outcome
    assert json.loads(state["messages"][-1]["content"]) == observation


def test_action_rejects_mutated_state_before_mcp_call(tmp_path):
    class CountingClient:
        calls = 0

        async def call_tool(self, name, arguments):
            self.calls += 1

    client = CountingClient()
    state = initial_state("task-1", "a" * 32, "b" * 16, "分析门店 A")
    state["selected_tool"] = "get_store_net"
    state["tool_arguments"] = {"store_id": "A", "db_path": "/tmp/other.db"}
    with pytest.raises(ValueError, match="无效工具或参数"):
        asyncio.run(make_tool_node(client, str(tmp_path / "trace.jsonl"))(state))
    assert client.calls == 0


@pytest.mark.parametrize("response, error, expected_outcome", [
    (SimpleNamespace(is_error=True, structured_content=None), None, "dependency_error"),
    (None, asyncio.TimeoutError(), "timeout"),
])
def test_expected_tool_failure_becomes_observation(tmp_path, response, error, expected_outcome):
    class FailingClient:
        async def call_tool(self, name, arguments):
            if error is not None:
                raise error
            return response

    trace_path = tmp_path / "trace.jsonl"
    model = FixedModel("get_store_net", {"store_id": "A"})
    graph = build_single_turn_graph(model, make_tool_node(FailingClient(), str(trace_path)))
    state = asyncio.run(graph.ainvoke(initial_state("task-1", "a" * 32, "b" * 16, "查询门店 A")))
    (span,) = read_spans(str(trace_path))
    assert state["last_tool_result"]["outcome"] == expected_outcome
    assert span["attributes"]["outcome"] == expected_outcome
    assert state["tool_attempt"] == 1
    assert state["operation_id"] == span["attributes"]["operation_id"]


def test_trace_write_failure_is_not_swallowed(tmp_path, monkeypatch):
    class SuccessfulClient:
        async def call_tool(self, name, arguments):
            return SimpleNamespace(is_error=False, structured_content={"result": 12000})

    def fail_write(path, span):
        raise OSError("磁盘不可写")

    monkeypatch.setattr(observed_sql, "append_span", fail_write)
    graph = build_single_turn_graph(
        FixedModel("get_store_net", {"store_id": "A"}),
        make_tool_node(SuccessfulClient(), str(tmp_path / "trace.jsonl")),
    )
    with pytest.raises(OSError, match="磁盘不可写"):
        asyncio.run(graph.ainvoke(initial_state("task-1", "a" * 32, "b" * 16, "查询门店 A")))
