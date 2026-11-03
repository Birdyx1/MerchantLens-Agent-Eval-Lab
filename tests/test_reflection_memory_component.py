"""组件评测需能区分反思约束失败与检查点记忆丢失。"""

import json

from merchant_agent.agent.state import initial_state
from merchant_agent.evaluation.reflection_memory_component import (
    ReflectionCase, evaluate_memory_snapshot, evaluate_reflection_case,
)


def _state(outcome="timeout"):
    state = initial_state("task-a", "a" * 32, "b" * 16, "分析商家 A")
    state["selected_tool"] = "get_store_net"
    state["tool_arguments"] = {"store_id": "A"}
    state["last_tool_result"] = {"outcome": outcome}
    return state


def _decision(action):
    return json.dumps({"plan": ["根据失败观察调整"], "action": action})


def test_reflection_revised_action_is_allowed():
    case = ReflectionCase("revised", _decision({"type": "tool", "name": "get_store_net",
                                                 "arguments": {"store_id": "B"}}), True)
    assert evaluate_reflection_case(case, _state())["passed"]


def test_reflection_repeated_action_is_rejected_by_policy():
    case = ReflectionCase("repeat", _decision({"type": "tool", "name": "get_store_net",
                                                "arguments": {"store_id": "A"}}), False)
    result = evaluate_reflection_case(case, _state())
    assert result["passed"] and result["failure_layer"] == "reflection_policy"


def test_reflection_security_rejection_cannot_call_another_tool():
    case = ReflectionCase("unsafe", _decision({"type": "tool", "name": "get_store_net",
                                                "arguments": {"store_id": "B"}}), False)
    assert evaluate_reflection_case(case, _state("security_rejected"))["passed"]


def test_memory_snapshot_detects_missing_observation_message():
    observation = {"outcome": "timeout"}
    state = _state()
    state["last_tool_result"] = observation
    state["messages"].append({"role": "tool", "content": json.dumps(observation)})
    good = evaluate_memory_snapshot(case_id="memory", snapshot=state,
                                    expected_task_id="task-a", expected_trace_id="a" * 32,
                                    expected_observation=observation)
    assert good["passed"]
    state["messages"].pop()
    bad = evaluate_memory_snapshot(case_id="memory", snapshot=state,
                                   expected_task_id="task-a", expected_trace_id="a" * 32,
                                   expected_observation=observation)
    assert not bad["passed"] and not bad["checks"]["observation_message"]
