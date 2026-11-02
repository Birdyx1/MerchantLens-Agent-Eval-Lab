import asyncio
import json
import sqlite3

import pytest
from mcp import Client

from merchant_agent.agent.action import make_tool_node
from merchant_agent.agent.graph import build_observation_loop_graph
from merchant_agent.agent.model_port import ModelResponse
from merchant_agent.agent.state import initial_state
from merchant_agent.mcp_server import create_server
from merchant_agent.tracing.reader import read_spans


TOOL_ACTION = {"type": "tool", "name": "get_store_net", "arguments": {"store_id": "A"}}


class SequenceModel:
    def __init__(self, actions):
        self.actions = iter(actions)
        self.received = []

    async def generate(self, messages):
        self.received.append(messages)
        action = next(self.actions)
        text = json.dumps({"plan": ["查询并核对"], "action": action})
        return ModelResponse(text, "sequence-model", 10, 4)


def _database(tmp_path):
    db_path = tmp_path / "orders.sqlite"
    with sqlite3.connect(db_path) as db:
        db.execute("CREATE TABLE orders (order_id TEXT, store_id TEXT, paid_fen INTEGER, refunded_fen INTEGER)")
        db.execute("INSERT INTO orders VALUES ('1', 'A', 15000, 3000)")
    return db_path


def test_tool_observation_returns_to_planning(tmp_path):
    model = SequenceModel([TOOL_ACTION, {"type": "finish", "answer": "门店 A 净收入为 12000 分"}])
    trace_path = tmp_path / "trace.jsonl"

    async def run():
        async with Client(create_server(str(_database(tmp_path)))) as client:
            graph = build_observation_loop_graph(model, make_tool_node(client, str(trace_path)))
            return await graph.ainvoke(initial_state("task-1", "a" * 32, "b" * 16, "门店 A 净收入？"))

    state = asyncio.run(run())
    assert state["final_answer"] == "门店 A 净收入为 12000 分"
    assert state["termination_reason"] == "completed"
    assert state["step_count"] == 3
    assert (state["input_tokens"], state["output_tokens"]) == (20, 8)
    assert len(model.received) == 2
    assert model.received[1][-1]["role"] == "tool"
    assert json.loads(model.received[1][-1]["content"])["result_fen"] == 12000
    (span,) = read_spans(str(trace_path))
    assert span["attributes"]["outcome"] == "success"


@pytest.mark.parametrize("max_steps, expected_calls", [(1, 0), (2, 1), (3, 1)])
def test_budget_stops_repeated_tool_decisions(tmp_path, max_steps, expected_calls):
    model = SequenceModel([TOOL_ACTION] * 5)
    trace_path = tmp_path / "trace.jsonl"

    async def run():
        async with Client(create_server(str(_database(tmp_path)))) as client:
            graph = build_observation_loop_graph(model, make_tool_node(client, str(trace_path)))
            return await graph.ainvoke(initial_state(
                "task-1", "a" * 32, "b" * 16, "门店 A 净收入？", max_steps=max_steps
            ))

    state = asyncio.run(run())
    assert state["termination_reason"] == "max_steps"
    assert state["final_answer"] is None
    assert state["selected_tool"] is None
    assert state["step_count"] == max_steps
    spans = read_spans(str(trace_path)) if trace_path.exists() else []
    assert len(spans) == expected_calls
