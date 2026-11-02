import asyncio
import json

import pytest

from merchant_agent.agent.model_port import ModelResponse
from merchant_agent.agent.planning import make_plan_node, parse_planning_decision, route_after_plan
from merchant_agent.agent.state import initial_state


class FixedModel:
    def __init__(self, text: str):
        self.text = text
        self.messages = None

    async def generate(self, messages):
        self.messages = messages
        return ModelResponse(self.text, "fixed-model", 12, 5)


def test_plan_node_selects_sql_and_accounts_for_tokens():
    text = json.dumps({
        "plan": ["查询门店净收入"],
        "action": {"type": "tool", "name": "get_store_net", "arguments": {"store_id": "A"}},
    })
    model = FixedModel(text)
    state = initial_state("task-1", "a" * 32, "b" * 16, "门店 A 净收入？")
    update = asyncio.run(make_plan_node(model)(state))
    merged = state | update

    assert model.messages[0]["role"] == "system"
    assert model.messages[-1] == {"role": "user", "content": "门店 A 净收入？"}
    assert update["selected_tool"] == "get_store_net"
    assert update["tool_arguments"] == {"store_id": "A"}
    assert update["last_model_id"] == "fixed-model"
    assert (update["input_tokens"], update["output_tokens"]) == (12, 5)
    assert route_after_plan(merged) == "tool"


def test_plan_node_can_finish_without_tool():
    text = json.dumps({"plan": [], "action": {"type": "finish", "answer": "需要更多信息"}})
    state = initial_state("task-1", "a" * 32, "b" * 16, "问题不完整")
    update = asyncio.run(make_plan_node(FixedModel(text))(state))
    assert update["selected_tool"] is None
    assert update["final_answer"] == "需要更多信息"
    assert route_after_plan(state | update) == "finish"


@pytest.mark.parametrize("action", [
    {"type": "tool", "name": "delete_database", "arguments": {}},
    {"type": "tool", "name": "get_store_net", "arguments": {"store_id": "A", "db_path": "/tmp/x"}},
    {"type": "tool", "name": "search_web", "arguments": {"query": "商家", "limit": True}},
    {"type": "tool", "name": "execute_python", "arguments": {"code": "print(1)", "timeout_seconds": 9}},
    {"type": "finish", "answer": "  "},
])
def test_invalid_model_action_cannot_route_to_tool(action):
    text = json.dumps({"plan": ["检查"], "action": action})
    with pytest.raises(ValueError):
        parse_planning_decision(text)


def test_non_json_or_conflicting_route_rejected():
    with pytest.raises(ValueError):
        parse_planning_decision("```json\n{}\n```")
    state = initial_state("task-1", "a" * 32, "b" * 16, "问题")
    with pytest.raises(ValueError):
        route_after_plan(state)
    state["selected_tool"] = "get_store_net"
    state["final_answer"] = "完成"
    with pytest.raises(ValueError):
        route_after_plan(state)
