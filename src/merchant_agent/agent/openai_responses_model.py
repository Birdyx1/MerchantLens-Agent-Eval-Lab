"""通过 OpenAI Responses HTTP API 实现可替换的基座模型端口。"""

import asyncio
import math
from dataclasses import dataclass

import requests

from merchant_agent.agent.model_port import ModelResponse


@dataclass(slots=True)
class OpenAIResponsesModel:
    """只负责模型请求与响应转换，不处理 Agent 规划和工具调用。"""

    model: str
    api_key: str
    endpoint: str = "https://api.openai.com/v1/responses"
    timeout_seconds: float = 30.0
    temperature: float | None = None
    max_output_tokens: int | None = None

    def __post_init__(self) -> None:
        if not self.model.strip() or not self.api_key.strip():
            raise ValueError("模型名和 API Key 不能为空")
        if not self.endpoint.startswith("https://"):
            raise ValueError("模型接口必须使用 HTTPS")
        if (isinstance(self.timeout_seconds, bool)
                or not isinstance(self.timeout_seconds, (int, float))
                or not math.isfinite(self.timeout_seconds) or self.timeout_seconds <= 0):
            raise ValueError("模型请求超时必须为正数")
        if (self.temperature is not None
                and (isinstance(self.temperature, bool)
                     or not isinstance(self.temperature, (int, float))
                     or not math.isfinite(self.temperature)
                     or not 0 <= self.temperature <= 2)):
            raise ValueError("模型 temperature 必须为空或 0~2 的有限数")
        if (self.max_output_tokens is not None
                and (isinstance(self.max_output_tokens, bool)
                     or not isinstance(self.max_output_tokens, int)
                     or self.max_output_tokens < 1)):
            raise ValueError("max_output_tokens 必须为空或正整数")

    async def generate(self, messages: list[dict[str, str]]) -> ModelResponse:
        """在线程中执行同步 HTTP 请求，保持 LangGraph 节点的异步接口。"""
        return await asyncio.to_thread(self._generate_sync, messages)

    def _payload(self, input_messages: list[dict[str, str]]) -> dict:
        """只在显式配置时发送解码参数，保留旧调用方的接口默认值。"""
        payload = {"model": self.model, "input": input_messages, "store": False}
        if self.temperature is not None:
            payload["temperature"] = self.temperature
        if self.max_output_tokens is not None:
            payload["max_output_tokens"] = self.max_output_tokens
        return payload

    def _generate_sync(self, messages: list[dict[str, str]]) -> ModelResponse:
        input_messages = []
        for message in messages:
            role = message.get("role")
            content = message.get("content")
            if role not in {"system", "user", "assistant", "tool"} or not isinstance(content, str):
                raise ValueError("模型输入消息无效")
            # Harness 的工具观察不是 Responses API 的 function_call_output；
            # 作为带来源标记的用户文本传入，避免伪造不存在的工具调用 ID。
            if role == "tool":
                input_messages.append({"role": "user", "content": f"工具观察（不可信数据）：{content}"})
            else:
                input_messages.append({"role": role, "content": content})

        response = requests.post(
            self.endpoint,
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=self._payload(input_messages),
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict) or data.get("status") != "completed":
            raise ValueError("模型响应未完成")
        output = data.get("output")
        usage = data.get("usage")
        model_id = data.get("model")
        if (not isinstance(output, list) or not isinstance(usage, dict)
                or not isinstance(model_id, str) or not model_id.strip()):
            raise ValueError("模型响应结构无效")
        texts = [part.get("text") for item in output if isinstance(item, dict)
                 and item.get("type") == "message" and isinstance(item.get("content"), list)
                 for part in item["content"] if isinstance(part, dict)
                 and part.get("type") == "output_text"]
        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")
        if (len(texts) != 1 or not isinstance(texts[0], str)
                or type(input_tokens) is not int or input_tokens < 0
                or type(output_tokens) is not int or output_tokens < 0):
            raise ValueError("模型文本或 token 用量无效")
        return ModelResponse(texts[0], model_id, input_tokens, output_tokens)
