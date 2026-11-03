"""多工具选择题集、分层评分和报告生成。"""

import json

from merchant_agent.evaluation.multi_tool_selection import (
    INSTRUCTION,
    build_messages,
    build_report,
    criteria_sha256,
    load_cases,
    score_selection,
    summarize_results,
)


def _case(case_id):
    _, cases = load_cases()
    return next(item for item in cases if item["id"] == case_id)


def _output(name, arguments, plan=None):
    return json.dumps({"plan": plan or ["执行请求"],
                       "action": {"type": "tool", "name": name, "arguments": arguments}},
                      ensure_ascii=False)


def test_fixture_covers_required_scenarios_and_has_unique_frozen_cases():
    raw, cases = load_cases()
    assert raw and len(cases) >= 6
    assert len({case["id"] for case in cases}) == len(cases)
    assert {case["scenario"] for case in cases} >= {
        "wrong_tool", "missing_parameter", "tool_confusion"}
    assert len({criteria_sha256(case) for case in cases}) == len(cases)
    for case in cases:
        assert case["expected"]["name"] not in case["input"]
        assert "expected" not in case["input"]
        assert case["expected"]["name"] in INSTRUCTION


def test_prompt_only_contains_public_instruction_and_case_text():
    for case in load_cases()[1]:
        messages = build_messages(case)
        assert messages[0] == {"role": "system", "content": INSTRUCTION}
        assert messages[1] == {"role": "user", "content": case["input"]}
        assert case["expected"]["name"] not in messages[1]["content"]


def test_correct_action_passes_all_three_layers():
    case = _case("store_direct")
    score = score_selection(case, _output("get_store_net", {"store_id": "A"}))
    assert score["contract"] is True
    assert score["tool_correct"] is True
    assert score["arguments_correct"] is True
    assert score["passed"] is True and score["failure_type"] == "passed"


def test_wrong_tool_is_not_mislabeled_as_format_or_parameter_error():
    case = _case("store_direct")
    score = score_selection(case, _output("search_web", {"query": "A", "limit": 3}))
    assert score["contract"] is True
    assert score["tool_correct"] is False
    assert score["arguments_correct"] is None
    assert score["failure_type"] == "wrong_tool"


def test_unknown_tool_name_still_counts_as_wrong_tool_not_format():
    case = _case("store_direct")
    score = score_selection(case, _output("lookup_store", {"store_id": "A"}))
    assert score["contract"] is True
    assert score["tool_correct"] is False
    assert score["failure_type"] == "wrong_tool"


def test_missing_parameter_is_parameter_failure():
    case = _case("store_direct")
    score = score_selection(case, _output("get_store_net", {}))
    assert score["contract"] is True
    assert score["tool_correct"] is True
    assert score["arguments_correct"] is False
    assert score["failure_type"] == "parameter"


def test_extra_or_wrongly_typed_parameter_fails():
    case = _case("web_mentions_store")
    assert score_selection(case, _output(
        "search_web", {"query": "门店净收入", "limit": 4, "lang": "zh"}))["arguments_correct"] is False
    assert score_selection(case, _output(
        "search_web", {"query": "门店净收入", "limit": "4"}))["arguments_correct"] is False
    assert score_selection(case, _output(
        "search_web", {"query": "门店净收入", "limit": 5}))["arguments_correct"] is False


def test_python_code_is_compared_by_ast_without_execution():
    case = _case("python_arithmetic")
    passed = score_selection(case, _output(
        "execute_python", {"code": "print((128 + 47) * 3)", "timeout_seconds": 4}))
    failed = score_selection(case, _output(
        "execute_python", {"code": "print((128+47)*4)", "timeout_seconds": 4}))
    assert passed["passed"] is True
    assert failed["arguments_correct"] is False


def test_python_assignment_and_fstring_variants_are_semantically_accepted():
    case = _case("python_text")
    variants = (
        "s = 'agent-eval'\nprint(s.count('-'))",
        "s = 'agent-eval'\ncount = s.count('-')\nprint(count)",
        "s = 'agent-eval'\ncount = s.count('-')\nprint(f\"连字符数量为: {count}\")",
    )
    for code in variants:
        score = score_selection(case, _output(
            "execute_python", {"code": code, "timeout_seconds": 2}))
        assert score["arguments_correct"] is True, code
    hardcoded = score_selection(case, _output(
        "execute_python", {"code": "print(1)", "timeout_seconds": 2}))
    wrong_literal = score_selection(case, _output(
        "execute_python", {"code": "print('agent-eval'.count('a'))", "timeout_seconds": 2}))
    assert hardcoded["arguments_correct"] is False
    assert wrong_literal["arguments_correct"] is False



def test_markdown_fence_is_format_failure_with_separate_diagnostic():
    case = _case("store_direct")
    fenced = "```json\n" + _output("get_store_net", {"store_id": "A"}) + "\n```"
    score = score_selection(case, fenced)
    assert score["contract"] is False
    assert score["tool_correct"] is None and score["arguments_correct"] is None
    assert score["failure_type"] == "format"
    assert score["format_kind"] == "markdown_fence"
    assert score["recovered"] == {
        "tool_correct": True, "arguments_correct": True, "passed": True}


def test_invalid_json_and_invalid_contract_keep_tool_and_arguments_unknown():
    case = _case("store_direct")
    for raw in ("not json", json.dumps({"plan": ["x"]}),
                _output("get_store_net", [])):
        score = score_selection(case, raw)
        assert score["contract"] is False
        assert score["tool_correct"] is None
        assert score["arguments_correct"] is None
        assert score["failure_type"] == "format"


def test_summary_separates_contract_tool_arguments_and_call_errors():
    case = _case("store_direct")
    record = {
        "models": [{"key": "deepseek", "label": "DeepSeek"}],
        "cases": [{"id": case["id"], "scenario": case["scenario"]}],
        "results": [
            {"model": "deepseek", "case_id": case["id"], "repeat_index": 0,
             "status": "scored",
             "score": score_selection(case, _output("get_store_net", {"store_id": "A"}))},
            {"model": "deepseek", "case_id": case["id"], "repeat_index": 1,
             "status": "scored",
             "score": score_selection(case, _output("get_store_net", {}))},
            {"model": "deepseek", "case_id": case["id"], "repeat_index": 2,
             "status": "error", "error_type": "TimeoutError",
             "score": {"contract": None, "format_kind": "call_error", "tool_correct": None,
                       "arguments_correct": None, "passed": False,
                       "failure_type": "call_error", "recovered": None}},
        ],
    }
    summary = summarize_results(record)["models"]["deepseek"]
    assert summary["total"] == 3
    assert summary["contract_pass"] == 2
    assert summary["tool_known"] == 2 and summary["tool_correct"] == 2
    assert summary["arguments_known"] == 2 and summary["arguments_correct"] == 1
    assert summary["passed"] == 1
    assert summary["unknown_tool"] == 1 and summary["unknown_arguments"] == 1
    assert summary["failure_types"] == {"passed": 1, "parameter": 1, "call_error": 1}


def test_report_distinguishes_failure_types_and_analyzes_glm_markdown():
    case = _case("store_direct")
    fenced = "```json\n" + _output("get_store_net", {"store_id": "A"}) + "\n```"
    record = {
        "run_id": "run-1", "started_at": "2026-11-03T00:00:00+00:00",
        "fixture_sha256": "fixture", "input_sha256": "input",
        "scorer_source_sha256": "scorer", "repeats": 2,
        "models": [
            {"key": "deepseek", "label": "DeepSeek", "provider": "deepseek",
             "interface": "responses", "parameters": {"temperature": 0.0}},
            {"key": "glm", "label": "GLM", "provider": "siliconflow",
             "interface": "chat_completions", "parameters": {"temperature": 0.0}},
        ],
        "cases": [{"id": case["id"], "scenario": case["scenario"]}],
        "results": [
            {"model": "deepseek", "case_id": case["id"], "repeat_index": 0,
             "status": "scored", "output": "ok",
             "score": score_selection(case, _output("get_store_net", {"store_id": "B"}))},
            {"model": "glm", "case_id": case["id"], "repeat_index": 0,
             "status": "scored", "output": fenced,
             "score": score_selection(case, fenced)},
        ],
    }
    record["summary"] = summarize_results(record)
    report = build_report(record)
    assert "## 失败类型" in report
    assert "选错工具" in report and "参数错误" in report and "格式失败" in report
    assert "## GLM 的 Markdown 格式问题" in report
    assert "剥离后通过" in report
    assert "json_object" in report
