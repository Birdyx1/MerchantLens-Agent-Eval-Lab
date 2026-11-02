import asyncio
import json

import pytest

from merchant_agent.agent.graph import build_observation_loop_graph
from merchant_agent.agent.model_port import ModelResponse
from merchant_agent.agent.runner import run_agent
from merchant_agent.agent.state import initial_state


class FixedModel:
    def __init__(self, action):
        self.action = action
        self.calls = 0

    async def generate(self, messages):
        self.calls += 1
        return ModelResponse(json.dumps({"plan": ["检查预算"], "action": self.action}),
                             "fixed-model", 10, 4)


TOOL_ACTION = {"type": "tool", "name": "get_store_net", "arguments": {"store_id": "A"}}


def test_token_budget_blocks_tool_after_model_usage():
    model = FixedModel(TOOL_ACTION)
    tool_calls = []

    async def tool_node(state):
        tool_calls.append(state)
        return {"step_count": 1}

    graph = build_observation_loop_graph(model, tool_node)
    state = asyncio.run(run_agent(graph, initial_state(
        "task-1", "a" * 32, "b" * 16, "问题", max_total_tokens=10
    )))
    assert model.calls == 1
    assert tool_calls == []
    assert state["termination_reason"] == "max_tokens"
    assert state["final_answer"] is None
    assert (state["input_tokens"], state["output_tokens"]) == (10, 4)


def test_large_step_budget_ends_by_project_policy():
    class RepeatedModel:
        async def generate(self, messages):
            return ModelResponse(json.dumps({"plan": ["查询"], "action": TOOL_ACTION}),
                                 "fixed-model", 1, 0)

    async def tool_node(state):
        return {"last_tool_result": {"tool_name": "get_store_net", "outcome": "success"},
                "step_count": 1}

    graph = build_observation_loop_graph(RepeatedModel(), tool_node)
    state = asyncio.run(run_agent(graph, initial_state(
        "task-1", "a" * 32, "b" * 16, "问题", max_steps=30, max_total_tokens=1000
    )))
    assert state["step_count"] == 30
    assert state["termination_reason"] == "max_steps"
    assert state["final_answer"] is None


@pytest.mark.parametrize("limit", [0, -1, True])
def test_invalid_token_budget_rejected(limit):
    with pytest.raises(ValueError, match="max_total_tokens"):
        initial_state("task-1", "a" * 32, "b" * 16, "问题", max_total_tokens=limit)
