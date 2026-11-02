import asyncio
import json

import pytest

from merchant_agent.agent.graph import build_single_turn_graph
from merchant_agent.agent.model_port import ModelResponse
from merchant_agent.agent.state import initial_state


class FixedModel:
    def __init__(self, action):
        self.action = action

    async def generate(self, messages):
        return ModelResponse(json.dumps({"plan": ["执行当前步骤"], "action": self.action}),
                             "fixed-model", 10, 4)


def _initial():
    return initial_state("task-1", "a" * 32, "b" * 16, "门店 A 净收入？")


def test_conditional_edge_enters_tool_node():
    calls = []

    async def tool_node(state):
        calls.append((state["selected_tool"], state["tool_arguments"]))
        return {"last_tool_result": {"result_fen": 12000}, "step_count": 1}

    model = FixedModel({"type": "tool", "name": "get_store_net", "arguments": {"store_id": "A"}})
    state = asyncio.run(build_single_turn_graph(model, tool_node).ainvoke(_initial()))
    assert calls == [("get_store_net", {"store_id": "A"})]
    assert state["last_tool_result"] == {"result_fen": 12000}
    assert state["step_count"] == 2
    assert (state["input_tokens"], state["output_tokens"]) == (10, 4)
    assert state["final_answer"] is None


def test_finish_branch_skips_tool_node():
    calls = []

    async def tool_node(state):
        calls.append(state)
        return {}

    model = FixedModel({"type": "finish", "answer": "需要明确门店"})
    state = asyncio.run(build_single_turn_graph(model, tool_node).ainvoke(_initial()))
    assert calls == []
    assert state["final_answer"] == "需要明确门店"
    assert state["step_count"] == 1


def test_invalid_tool_decision_never_reaches_action():
    calls = []

    async def tool_node(state):
        calls.append(state)
        return {}

    model = FixedModel({"type": "tool", "name": "delete_database", "arguments": {}})
    graph = build_single_turn_graph(model, tool_node)
    with pytest.raises(ValueError, match="工具名或工具参数无效"):
        asyncio.run(graph.ainvoke(_initial()))
    assert calls == []
