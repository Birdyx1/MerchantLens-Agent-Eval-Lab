"""冻结反思输出与检查点快照，分别评测决策约束和短期记忆。"""

import json
from dataclasses import dataclass
from typing import Mapping

from merchant_agent.agent.planning import parse_planning_decision, validate_reflection_decision
from merchant_agent.agent.state import AgentState


@dataclass(frozen=True, slots=True)
class ReflectionCase:
    case_id: str
    model_output: str
    expected_allowed: bool


def evaluate_reflection_case(case: ReflectionCase, state: AgentState) -> dict:
    """用真实解析器和反思约束重放一次失败后的模型决策。"""
    try:
        decision = parse_planning_decision(case.model_output)
    except ValueError as exc:
        allowed, layer, reason = False, "model_contract", str(exc)
    else:
        try:
            validate_reflection_decision(state, decision)
        except ValueError as exc:
            allowed, layer, reason = False, "reflection_policy", str(exc)
        else:
            allowed, layer, reason = True, None, "反思决策通过"
    return {
        "case_id": case.case_id,
        "passed": allowed == case.expected_allowed,
        "observed_allowed": allowed,
        "failure_layer": layer,
        "reason": reason,
    }


def evaluate_memory_snapshot(
    *, case_id: str, snapshot: Mapping, expected_task_id: str,
    expected_trace_id: str, expected_observation: dict,
) -> dict:
    """校验真实 Checkpointer 快照是否保留身份和最新工具观察。"""
    messages = snapshot.get("messages")
    tool_messages = ([message for message in messages if isinstance(message, dict)
                      and message.get("role") == "tool"] if isinstance(messages, list) else [])
    try:
        latest_message = json.loads(tool_messages[-1]["content"]) if tool_messages else None
    except (TypeError, ValueError, KeyError):
        latest_message = None
    checks = {
        "task_isolation": snapshot.get("task_id") == expected_task_id,
        "trace_isolation": snapshot.get("trace_id") == expected_trace_id,
        "observation_state": snapshot.get("last_tool_result") == expected_observation,
        "observation_message": latest_message == expected_observation,
    }
    return {"case_id": case_id, "passed": all(checks.values()), "checks": checks}
