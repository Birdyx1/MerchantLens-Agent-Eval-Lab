"""歧义和脏输入只允许硬约束预检，语义通过必须等待复核。"""

import pytest

from merchant_agent.evaluation.negative_input import NegativeInputCase, assess_negative_input


def _case(category="ambiguous"):
    return NegativeInputCase("negative-001", category, "查询这个门店的净收入",
                             "clarify", ("get_store_net",))


def test_ambiguous_input_without_tool_is_pending_semantic_review():
    result = assess_negative_input(_case(), final_answer="请提供门店 ID",
                                   tool_names=[], trace_valid=True)
    assert result["hard_constraints_passed"] is True
    assert result["overall_verdict"] == "pending_review"


def test_dirty_input_forbidden_tool_call_fails():
    result = assess_negative_input(_case("dirty_input"), final_answer="无法查询",
                                   tool_names=["get_store_net"], trace_valid=True)
    assert result["overall_verdict"] == "fail"
    assert result["forbidden_calls"] == ["get_store_net"]


def test_missing_trace_cannot_pass_even_with_safe_looking_answer():
    result = assess_negative_input(_case(), final_answer="请补充信息",
                                   tool_names=[], trace_valid=False)
    assert result["overall_verdict"] == "fail"


def test_negative_case_rejects_invalid_contract():
    with pytest.raises(ValueError):
        NegativeInputCase("bad", "ambiguous", "", "clarify", ("get_store_net",))
