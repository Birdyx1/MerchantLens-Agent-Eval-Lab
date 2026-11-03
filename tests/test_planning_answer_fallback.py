import pytest

from merchant_agent.agent.planning import parse_planning_decision


def test_parse_accepts_plain_text_as_finish_answer():
    # 模型拿到工具结果后可能直接输出 Markdown 答案；应容错为 finish，而不是让 Trial 报错。
    text = "各渠道退款率：\n\n| channel | refund_rate |\n|---|---|\n| 堂食 | 0.0279 |"
    decision = parse_planning_decision(text)
    assert decision.tool_name is None
    assert decision.final_answer == text.strip()
    assert decision.plan == []


def test_parse_rejects_malformed_json_object():
    # 以 { 开头但不是合法 JSON：仍应报错，不能把坏 JSON 当答案。
    with pytest.raises(ValueError):
        parse_planning_decision('{"plan": ["x"], "action": }')


def test_parse_rejects_empty_text():
    with pytest.raises(ValueError):
        parse_planning_decision("   ")
