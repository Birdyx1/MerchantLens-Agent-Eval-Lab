"""将 DeepSeek Responses API 接入通用模型端口。"""

from merchant_agent.agent.openai_responses_model import OpenAIResponsesModel


class DeepSeekResponsesModel(OpenAIResponsesModel):
    """沿用 Responses 响应解析，固定 DeepSeek 官方接口地址。"""

    def __init__(self, model: str, api_key: str, *, timeout_seconds: float = 30.0,
                 temperature: float | None = None,
                 max_output_tokens: int | None = None) -> None:
        super().__init__(model, api_key, "https://api.deepseek.com/responses",
                         timeout_seconds, temperature, max_output_tokens)
