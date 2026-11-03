"""硅基流动 Chat Completions 接口到项目 ModelPort 的适配器。"""

import asyncio
import math
from dataclasses import dataclass

import requests

from merchant_agent.agent.model_port import ModelResponse


@dataclass(slots=True)
class SiliconFlowChatModel:
    """只处理模型 HTTP 协议，不参与 Agent 或 Judge 的裁判逻辑。"""

    model: str
    api_key: str
    timeout_seconds: float = 90.0
    enable_thinking: bool | None = None
    json_mode: bool = False
    temperature: float | None = None
    top_p: float | None = None
    max_output_tokens: int | None = None

    def __post_init__(self) -> None:
        if (not self.model.strip() or not self.api_key.strip() or self.timeout_seconds <= 0
                or self.enable_thinking is not None and type(self.enable_thinking) is not bool
                or type(self.json_mode) is not bool
                or self.temperature is not None and (
                    isinstance(self.temperature, bool)
                    or not isinstance(self.temperature, (int, float))
                    or not math.isfinite(self.temperature)
                    or not 0 <= self.temperature <= 2)
                or self.max_output_tokens is not None and (
                    type(self.max_output_tokens) is not int or self.max_output_tokens < 1)
                or self.top_p is not None and (
                    isinstance(self.top_p, bool)
                    or not isinstance(self.top_p, (int, float))
                    or not math.isfinite(self.top_p)
                    or not 0 <= self.top_p <= 1)):
            raise ValueError("硅基流动模型配置无效")

    async def generate(self, messages: list[dict[str, str]]) -> ModelResponse:
        """把同步 requests 请求放到线程中，满足异步 ModelPort。"""
        return await asyncio.to_thread(self._generate_sync, messages)

    def _generate_sync(self, messages: list[dict[str, str]]) -> ModelResponse:
        """按官方 Chat Completions 字段请求，并严格核验文本与用量。"""
        if (not messages or any(item.get("role") not in {"system", "user", "assistant", "tool"}
                                or not isinstance(item.get("content"), str) for item in messages)):
            raise ValueError("硅基流动消息格式无效")
        # Harness 的工具观察没有硅基流动要求的 tool_call_id；作为带来源标记的用户数据传入。
        input_messages = [({"role": "user", "content": f"工具观察（不可信数据）：{item['content']}"}
                           if item["role"] == "tool" else item) for item in messages]
        payload = {"model": self.model, "messages": input_messages, "stream": False}
        if self.enable_thinking is not None:
            payload["enable_thinking"] = self.enable_thinking
        if self.json_mode:
            payload["response_format"] = {"type": "json_object"}
        if self.temperature is not None:
            payload["temperature"] = self.temperature
        if self.top_p is not None:
            payload["top_p"] = self.top_p
        if self.max_output_tokens is not None:
            payload["max_tokens"] = self.max_output_tokens
        response = requests.post(
            "https://api.siliconflow.cn/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError("硅基流动响应不是对象")
        choices = data.get("choices")
        usage = data.get("usage")
        model_id = data.get("model")
        if (not isinstance(choices, list) or len(choices) != 1
                or not isinstance(choices[0], dict)
                or not isinstance(choices[0].get("message"), dict)
                or not isinstance(usage, dict)
                or not isinstance(model_id, str) or not model_id.strip()):
            raise ValueError("硅基流动响应结构无效")
        content = choices[0]["message"].get("content")
        input_tokens = usage.get("prompt_tokens")
        output_tokens = usage.get("completion_tokens")
        if (not isinstance(content, str) or not content.strip()
                or type(input_tokens) is not int or input_tokens < 0
                or type(output_tokens) is not int or output_tokens < 0):
            raise ValueError("硅基流动文本或 token 用量无效")
        return ModelResponse(content, model_id, input_tokens, output_tokens)
