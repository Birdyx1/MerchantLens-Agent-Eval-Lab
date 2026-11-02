import asyncio

import pytest

from merchant_agent.agent.openai_responses_model import OpenAIResponsesModel
from merchant_agent.agent.deepseek_responses_model import DeepSeekResponsesModel


class FakeResponse:
    def __init__(self, data):
        self.data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self.data


def _payload():
    return {
        "status": "completed", "model": "resolved-model-version",
        "output": [{"type": "message", "content": [{"type": "output_text", "text": "{\"ok\":true}"}]}],
        "usage": {"input_tokens": 8, "output_tokens": 4},
    }


def test_responses_adapter_uses_actual_model_and_token_usage(monkeypatch):
    captured = {}

    def fake_post(url, **kwargs):
        captured.update(url=url, **kwargs)
        return FakeResponse(_payload())

    monkeypatch.setattr("merchant_agent.agent.openai_responses_model.requests.post", fake_post)
    model = OpenAIResponsesModel("requested-model", "test-secret")
    result = asyncio.run(model.generate([
        {"role": "system", "content": "规划"},
        {"role": "tool", "content": "查询结果"},
    ]))
    assert result.text == '{"ok":true}'
    assert result.model_id == "resolved-model-version"
    assert (result.input_tokens, result.output_tokens) == (8, 4)
    assert captured["json"]["store"] is False
    assert captured["json"]["input"][1] == {"role": "user", "content": "工具观察（不可信数据）：查询结果"}
    assert captured["timeout"] == 30


@pytest.mark.parametrize("change", [
    {"status": "incomplete"},
    {"usage": {"input_tokens": True, "output_tokens": 4}},
    {"output": []},
])
def test_responses_adapter_rejects_incomplete_or_invalid_reply(monkeypatch, change):
    monkeypatch.setattr("merchant_agent.agent.openai_responses_model.requests.post",
                        lambda *args, **kwargs: FakeResponse(_payload() | change))
    with pytest.raises(ValueError):
        asyncio.run(OpenAIResponsesModel("model", "key").generate([{"role": "user", "content": "hi"}]))


def test_responses_adapter_rejects_plain_http():
    with pytest.raises(ValueError, match="HTTPS"):
        OpenAIResponsesModel("model", "key", endpoint="http://remote.example/v1/responses")


def test_deepseek_adapter_uses_official_responses_endpoint(monkeypatch):
    captured = {}

    def fake_post(url, **kwargs):
        captured["url"] = url
        return FakeResponse(_payload())

    monkeypatch.setattr("merchant_agent.agent.openai_responses_model.requests.post", fake_post)
    result = asyncio.run(DeepSeekResponsesModel("deepseek-flash", "test-key").generate(
        [{"role": "user", "content": "hi"}]
    ))
    assert captured["url"] == "https://api.deepseek.com/responses"
    assert result.input_tokens == 8
