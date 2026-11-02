import asyncio
import json
import sqlite3
from pathlib import Path

from jsonschema import Draft202012Validator
from mcp import Client

from merchant_agent.agent.action import make_tool_node
from merchant_agent.agent.graph import build_observation_loop_graph
from merchant_agent.agent.model_port import ModelResponse
from merchant_agent.agent.runner import run_agent
from merchant_agent.agent.state import initial_state
from merchant_agent.mcp_server import create_server
from merchant_agent.tracing.reader import read_spans
from merchant_agent.tracing.validator import validate_trace


class EvidenceModel:
    """必须看到真实工具观察才给出最终答案。"""

    async def generate(self, messages):
        observations = [json.loads(item["content"]) for item in messages if item["role"] == "tool"]
        if not observations:
            action = {"type": "tool", "name": "get_store_net", "arguments": {"store_id": "A"}}
        else:
            assert len(observations) == 1
            assert observations[0]["outcome"] == "success"
            action = {"type": "finish", "answer": f"门店 A 净收入为 {observations[0]['result_fen']} 分"}
        return ModelResponse(json.dumps({"plan": ["查询并核对"], "action": action}),
                             "evidence-model", 8, 4)


def test_full_agent_run_has_model_tool_and_root_trace(tmp_path):
    db_path = tmp_path / "orders.sqlite"
    with sqlite3.connect(db_path) as db:
        db.execute("CREATE TABLE orders (order_id TEXT, store_id TEXT, paid_fen INTEGER, refunded_fen INTEGER)")
        db.execute("INSERT INTO orders VALUES ('1', 'A', 15000, 3000)")
    trace_path = tmp_path / "trace.jsonl"
    initial = initial_state("task-1", "a" * 32, "b" * 16, "门店 A 净收入？")

    async def execute():
        async with Client(create_server(str(db_path))) as client:
            graph = build_observation_loop_graph(
                EvidenceModel(), make_tool_node(client, str(trace_path)), trace_path=str(trace_path)
            )
            return await run_agent(graph, initial, trace_path=str(trace_path))

    state = asyncio.run(execute())
    assert state["final_answer"] == "门店 A 净收入为 12000 分"
    assert state["termination_reason"] == "completed"
    assert state["step_count"] == 3
    assert (state["input_tokens"], state["output_tokens"]) == (16, 8)

    spans = read_spans(str(trace_path))
    schema = json.loads((Path(__file__).resolve().parents[1] / "schemas/span.schema.json").read_text())
    assert len(spans) == 4
    assert all(Draft202012Validator(schema).is_valid(span) for span in spans)
    assert validate_trace(spans) == []
    assert [span["name"] for span in spans] == [
        "model.plan", "tool.get_store_net", "model.plan", "agent.request"
    ]
    assert all(span["trace_id"] == initial["trace_id"] for span in spans)
    assert all(span["parent_span_id"] == initial["root_span_id"] for span in spans[:-1])
    assert spans[-1]["span_id"] == initial["root_span_id"]
    assert spans[1]["attributes"]["result_fen"] == 12000
    assert spans[2]["attributes"]["action_type"] == "finish"
    assert spans[-1]["attributes"]["termination_reason"] == "completed"
