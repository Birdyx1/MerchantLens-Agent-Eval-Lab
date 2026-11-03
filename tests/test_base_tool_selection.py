import json

from merchant_agent.evaluation.base_tool_selection import load_cases, score_selection


def _output(name, arguments):
    return json.dumps({"plan": ["执行请求"], "action": {"type": "tool", "name": name, "arguments": arguments}})


def test_wrong_tool_and_wrong_parameter_are_distinct():
    _, cases = load_cases()
    case = cases[0]
    wrong_tool = score_selection(case, _output("search_web", {"query": "A", "limit": 3}))
    wrong_parameter = score_selection(case, _output("get_store_net", {"store_id": "B"}))
    assert wrong_tool["contract"] and not wrong_tool["tool_correct"]
    assert wrong_parameter["tool_correct"] and not wrong_parameter["arguments_correct"]


def test_python_whitespace_is_accepted_without_executing_code():
    _, cases = load_cases()
    case = cases[-1]
    assert score_selection(case, _output("execute_python", {"code": "print(6 * 7)", "timeout_seconds": 2}))["passed"]
    assert not score_selection(case, _output("execute_python", {"code": "print(6 * 8)", "timeout_seconds": 2}))["passed"]


def test_invalid_json_is_not_mislabeled_as_wrong_tool():
    _, cases = load_cases()
    result = score_selection(cases[0], "```json\n{}\n```")
    assert result["contract"] is False
    assert result["tool_correct"] is None and result["arguments_correct"] is None
