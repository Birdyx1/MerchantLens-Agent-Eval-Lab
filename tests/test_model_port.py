import asyncio
from dataclasses import FrozenInstanceError

import pytest

from merchant_agent.agent.model_port import ModelPort, ModelResponse


def test_model_port_accepts_replaceable_implementation():
    class FixedModel:
        async def generate(self, messages: list[dict[str, str]]) -> ModelResponse:
            assert messages == [{"role": "user", "content": "门店 A 净收入是多少？"}]
            return ModelResponse("需要查询 SQL", "fixed-model", 12, 5)

    model: ModelPort = FixedModel()
    response = asyncio.run(model.generate([{"role": "user", "content": "门店 A 净收入是多少？"}]))
    assert response.text == "需要查询 SQL"
    assert response.model_id == "fixed-model"
    assert (response.input_tokens, response.output_tokens) == (12, 5)


def test_model_response_is_immutable():
    response = ModelResponse("结果", "fixed-model", 1, 1)
    with pytest.raises(FrozenInstanceError):
        response.text = "被修改"
