import asyncio
import json
from types import SimpleNamespace

import pytest

from merchant_agent.agent.action import make_tool_node
from merchant_agent.agent.graph import build_observation_loop_graph
from merchant_agent.agent.model_port import ModelResponse
from merchant_agent.agent.planning import REFLECTION_INSTRUCTION, make_plan_node
from merchant_agent.agent.state import initial_state
from merchant_agent.tracing.reader import read_spans


class SequenceModel:
    def __init__(self, actions):
        self.actions = iter(actions)
        self.received = []

    async def generate(self, messages):
        self.received.append(messages)
        action = next(self.actions)
        return ModelResponse(json.dumps({"plan": ["根据观察调整"], "action": action}),
                             "fixed-model", 10, 4)


SQL_ACTION = {"type": "tool", "name": "get_store_net", "arguments": {"store_id": "A"}}
SEARCH_ACTION = {"type": "tool", "name": "search_web", "arguments": {"query": "商家", "limit": 1}}


def test_failure_observation_leads_to_revised_tool_decision(tmp_path):
    class Client:
        async def call_tool(self, name, arguments):
            if name == "get_store_net":
                return SimpleNamespace(is_error=True, structured_content=None)
            return SimpleNamespace(is_error=False, structured_content={
                "query": "商家", "results": [{"title": "商家指南", "url": "https://example.com"}]
            })

    model = SequenceModel([SQL_ACTION, SEARCH_ACTION,
                           {"type": "finish", "answer": "SQL 不可用，已找到相关资料"}])
    trace_path = tmp_path / "trace.jsonl"
    graph = build_observation_loop_graph(model, make_tool_node(Client(), str(trace_path)))
    state = asyncio.run(graph.ainvoke(initial_state("task-1", "a" * 32, "b" * 16, "分析门店 A")))
    first, second = read_spans(str(trace_path))
    assert first["attributes"]["outcome"] == "dependency_error"
    assert second["attributes"]["outcome"] == "success"
    assert first["attributes"]["operation_id"] != second["attributes"]["operation_id"]
    assert model.received[1][1]["content"] == REFLECTION_INSTRUCTION
    assert model.received[1][-1]["role"] == "tool"
    assert state["final_answer"] == "SQL 不可用，已找到相关资料"
    assert state["retry_count"] == 0


@pytest.mark.parametrize("failure_outcome, next_action, error", [
    ("program_error", {"type": "tool", "name": "execute_python",
                       "arguments": {"code": "print(1)", "timeout_seconds": 2}}, "原样重复"),
    ("security_rejected", SEARCH_ACTION, "安全拒绝"),
])
def test_invalid_reflection_cannot_execute(failure_outcome, next_action, error):
    model = SequenceModel([next_action])
    state = initial_state("task-1", "a" * 32, "b" * 16, "分析门店 A")
    state["selected_tool"] = "execute_python"
    state["tool_arguments"] = {"code": "print(1)", "timeout_seconds": 2}
    state["last_tool_result"] = {"tool_name": "execute_python", "outcome": failure_outcome}
    with pytest.raises(ValueError, match=error):
        asyncio.run(make_plan_node(model)(state))
