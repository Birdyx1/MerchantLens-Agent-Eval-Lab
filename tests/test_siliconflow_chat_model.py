"""硅基流动模型适配器按 Chat Completions 协议转换响应。"""

from unittest.mock import Mock, patch

import pytest

from merchant_agent.agent.siliconflow_chat_model import SiliconFlowChatModel


def test_chat_response_is_mapped_to_model_port() -> None:
    reply = Mock()
    reply.json.return_value = {"model": "Qwen/Qwen3.8-27B",
                                 "choices": [{"message": {"content": '{"score":2,"reason":"清楚"}'}}],
                                 "usage": {"prompt_tokens": 20, "completion_tokens": 8}}
    with patch("merchant_agent.agent.siliconflow_chat_model.requests.post", return_value=reply) as post:
        result = SiliconFlowChatModel("Qwen/Qwen3.8-27B", "secret")._generate_sync(
            [{"role": "user", "content": "请评分"}])
    assert result.model_id == "Qwen/Qwen3.8-27B"
    assert (result.input_tokens, result.output_tokens) == (20, 8)
    assert post.call_args.kwargs["json"]["model"] == "Qwen/Qwen3.8-27B"
    assert post.call_args.args[0] == "https://api.siliconflow.cn/v1/chat/completions"


def test_missing_final_text_is_rejected() -> None:
    reply = Mock()
    reply.json.return_value = {"model": "zai-org/GLM-5.3-Flash",
                                 "choices": [{"message": {"content": None, "reasoning_content": "推理"}}],
                                 "usage": {"prompt_tokens": 20, "completion_tokens": 8}}
    with patch("merchant_agent.agent.siliconflow_chat_model.requests.post", return_value=reply):
        with pytest.raises(ValueError, match="文本或 token"):
            SiliconFlowChatModel("zai-org/GLM-5.3-Flash", "secret")._generate_sync(
                [{"role": "user", "content": "请评分"}])


def test_qwen_thinking_setting_is_sent_explicitly() -> None:
    reply = Mock()
    reply.json.return_value = {"model": "Qwen/Qwen3.8-27B",
                                 "choices": [{"message": {"content": "OK"}}],
                                 "usage": {"prompt_tokens": 5, "completion_tokens": 2}}
    with patch("merchant_agent.agent.siliconflow_chat_model.requests.post", return_value=reply) as post:
        SiliconFlowChatModel("Qwen/Qwen3.8-27B", "secret", enable_thinking=False)._generate_sync(
            [{"role": "user", "content": "请确认"}])
    assert post.call_args.kwargs["json"]["enable_thinking"] is False


def test_json_mode_is_opt_in() -> None:
    reply = Mock()
    reply.json.return_value = {"model": "zai-org/GLM-5.3-Flash",
                                 "choices": [{"message": {"content": '{"winner":"left","reason":"清楚"}'}}],
                                 "usage": {"prompt_tokens": 9, "completion_tokens": 5}}
    with patch("merchant_agent.agent.siliconflow_chat_model.requests.post", return_value=reply) as post:
        SiliconFlowChatModel("zai-org/GLM-5.3-Flash", "secret", json_mode=True)._generate_sync(
            [{"role": "user", "content": "请输出 JSON"}])
    assert post.call_args.kwargs["json"]["response_format"] == {"type": "json_object"}


def test_decoding_parameters_are_only_sent_when_explicitly_fixed() -> None:
    reply = Mock()
    reply.json.return_value = {"model": "zai-org/GLM-5.3-Flash",
                                 "choices": [{"message": {"content": "OK"}}],
                                 "usage": {"prompt_tokens": 5, "completion_tokens": 2}}
    with patch("merchant_agent.agent.siliconflow_chat_model.requests.post", return_value=reply) as post:
        SiliconFlowChatModel("zai-org/GLM-5.3-Flash", "secret",
                             temperature=0.0, top_p=1.0)._generate_sync(
            [{"role": "user", "content": "请确认"}])
    assert post.call_args.kwargs["json"]["temperature"] == 0.0
    assert post.call_args.kwargs["json"]["top_p"] == 1.0

    with patch("merchant_agent.agent.siliconflow_chat_model.requests.post", return_value=reply) as post:
        SiliconFlowChatModel("zai-org/GLM-5.3-Flash", "secret")._generate_sync(
            [{"role": "user", "content": "请确认"}])
    assert "temperature" not in post.call_args.kwargs["json"]
    assert "top_p" not in post.call_args.kwargs["json"]


def test_invalid_decoding_parameters_are_rejected() -> None:
    with pytest.raises(ValueError, match="配置无效"):
        SiliconFlowChatModel("zai-org/GLM-5.3-Flash", "secret", temperature=3)
    with pytest.raises(ValueError, match="配置无效"):
        SiliconFlowChatModel("zai-org/GLM-5.3-Flash", "secret", top_p=1.5)


def test_output_limit_is_validated_and_sent_when_configured() -> None:
    with pytest.raises(ValueError, match="配置无效"):
        SiliconFlowChatModel("test", "secret", max_output_tokens=True)
    with pytest.raises(ValueError, match="配置无效"):
        SiliconFlowChatModel("test", "secret", max_output_tokens=0)
    reply = Mock()
    reply.json.return_value = {"model": "test", "choices": [{"message": {"content": "OK"}}],
                              "usage": {"prompt_tokens": 1, "completion_tokens": 1}}
    with patch("merchant_agent.agent.siliconflow_chat_model.requests.post", return_value=reply) as post:
        SiliconFlowChatModel("test", "secret", max_output_tokens=2048)._generate_sync(
            [{"role": "user", "content": "test"}])
    assert post.call_args.kwargs["json"]["max_tokens"] == 2048


def test_tool_observation_is_passed_as_untrusted_user_text() -> None:
    reply = Mock()
    reply.json.return_value = {"model": "zai-org/GLM-5.3-Flash",
                                 "choices": [{"message": {"content": "OK"}}],
                                 "usage": {"prompt_tokens": 9, "completion_tokens": 5}}
    with patch("merchant_agent.agent.siliconflow_chat_model.requests.post", return_value=reply) as post:
        SiliconFlowChatModel("zai-org/GLM-5.3-Flash", "secret")._generate_sync(
            [{"role": "tool", "content": '{"result_fen":12000}'}])
    sent = post.call_args.kwargs["json"]["messages"]
    assert sent == [{"role": "user", "content": '工具观察（不可信数据）：{"result_fen":12000}'}]
