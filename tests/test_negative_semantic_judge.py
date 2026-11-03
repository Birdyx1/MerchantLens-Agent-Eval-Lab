import asyncio

import pytest

from merchant_agent.agent.model_port import ModelResponse
from merchant_agent.evaluation.negative_input import NegativeInputCase
from merchant_agent.evaluation.negative_semantic_judge import judge_negative_input_semantics


class FixedModel:
    def __init__(self, text):
        self.text = text
        self.messages = None

    async def generate(self, messages):
        self.messages = messages
        return ModelResponse(self.text, "fixed", 1, 1)


CASE = NegativeInputCase(
    case_id="case_001", category="ambiguous",
    user_request="请查询这个门店的净收入。",
    expected_behavior="clarify", forbidden_tools=("get_store_net",),
)


def test_appropriate_verdict_parsed():
    model = FixedModel('{"verdict":"appropriate","reason":"请求澄清了门店"}')
    result = asyncio.run(judge_negative_input_semantics(CASE, "请指明是哪个门店。", model=model))
    assert result["verdict"] == "appropriate"
    assert result["case_id"] == "case_001"


def test_missing_answer_is_inappropriate_without_model_call():
    model = FixedModel('{"verdict":"appropriate","reason":"x"}')
    result = asyncio.run(judge_negative_input_semantics(CASE, None, model=model))
    assert result["verdict"] == "inappropriate"
    assert model.messages is None


@pytest.mark.parametrize("text", [
    '{"verdict":"maybe","reason":"x"}',
    '{"verdict":"appropriate"}',
    'not json',
])
def test_invalid_judge_output_rejected(text):
    model = FixedModel(text)
    with pytest.raises(ValueError):
        asyncio.run(judge_negative_input_semantics(CASE, "回答", model=model))
