"""冻结模型输出后，单独评测规划解析与 Harness 路由。"""

from dataclasses import dataclass

from merchant_agent.agent.graph import _route_plan_with_budget
from merchant_agent.agent.planning import parse_planning_decision
from merchant_agent.agent.state import AgentState


@dataclass(frozen=True, slots=True)
class PlanningCase:
    case_id: str
    model_output: str
    expected_route: str
    expected_tool: str | None = None
    expected_arguments: dict | None = None


def evaluate_planning_case(case: PlanningCase, state: AgentState) -> dict:
    """解析错误归模型契约；合法输出路由错误归 Harness。"""
    try:
        decision = parse_planning_decision(case.model_output)
    except ValueError as exc:
        return {"case_id": case.case_id, "passed": False, "failure_layer": "model_contract",
                "observed_route": None, "reason": str(exc)}
    updated = dict(state)
    updated["selected_tool"] = decision.tool_name
    updated["tool_arguments"] = decision.tool_arguments
    updated["final_answer"] = decision.final_answer
    try:
        route = _route_plan_with_budget(updated)
    except ValueError as exc:
        return {"case_id": case.case_id, "passed": False, "failure_layer": "harness_route",
                "observed_route": None, "reason": str(exc)}
    passed = (route == case.expected_route and decision.tool_name == case.expected_tool
              and decision.tool_arguments == case.expected_arguments)
    return {"case_id": case.case_id, "passed": passed,
            "failure_layer": None if passed else "harness_route",
            "observed_route": route,
            "reason": "通过" if passed else "路由或工具参数与冻结期望不一致"}


def summarize_planning_cases(results: list[dict]) -> dict:
    """分别统计模型契约失败和 Harness 路由失败，保留分母。"""
    if not results or len({item["case_id"] for item in results}) != len(results):
        raise ValueError("组件评测需要非空且 ID 唯一的结果")
    return {"cases": len(results), "passed": sum(item["passed"] for item in results),
            "pass_rate": sum(item["passed"] for item in results) / len(results),
            "model_contract_failures": sum(item["failure_layer"] == "model_contract" for item in results),
            "harness_route_failures": sum(item["failure_layer"] == "harness_route" for item in results)}
