import json

from merchant_agent.agent.state import initial_state
from merchant_agent.evaluation import planning_component
from merchant_agent.evaluation.planning_component import (
    PlanningCase, evaluate_planning_case, summarize_planning_cases,
)


def _state():
    return initial_state("task_1", "a" * 32, "b" * 16, "查询 A 门店")


def _tool_output():
    return json.dumps({"plan": ["查询"], "action": {"type": "tool", "name": "get_store_net",
                                             "arguments": {"store_id": "A"}}})


def test_valid_model_output_routes_to_tool():
    result = evaluate_planning_case(PlanningCase("route_a", _tool_output(), "tool",
                                               "get_store_net", {"store_id": "A"}), _state())
    assert result["passed"] is True and result["failure_layer"] is None


def test_budget_route_is_evaluated_separately():
    state = _state()
    state["step_count"] = state["max_steps"]
    result = evaluate_planning_case(PlanningCase("budget", _tool_output(), "budget",
                                               "get_store_net", {"store_id": "A"}), state)
    assert result["passed"] is True and result["observed_route"] == "budget"


def test_invalid_model_contract_and_harness_mismatch_have_distinct_roots(monkeypatch):
    bad_model = evaluate_planning_case(PlanningCase("bad_model", "not-json", "tool"), _state())
    monkeypatch.setattr(planning_component, "_route_plan_with_budget", lambda state: "finish")
    mismatch = evaluate_planning_case(PlanningCase("mismatch", _tool_output(), "tool",
                                                 "get_store_net", {"store_id": "A"}), _state())
    summary = summarize_planning_cases([bad_model, mismatch])
    assert bad_model["failure_layer"] == "model_contract"
    assert mismatch["failure_layer"] == "harness_route"
    assert summary["model_contract_failures"] == summary["harness_route_failures"] == 1


def test_wrong_store_is_model_decision_not_harness_route():
    output = json.dumps({"plan": ["查询"], "action": {"type": "tool", "name": "get_store_net",
                                                       "arguments": {"store_id": "B"}}})
    result = evaluate_planning_case(PlanningCase("wrong_store", output, "tool",
                                               "get_store_net", {"store_id": "A"}), _state())
    assert result["failure_layer"] == "model_decision"
