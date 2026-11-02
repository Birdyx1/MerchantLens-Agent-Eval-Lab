from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ModelResponse:
    """模型适配层返回的文本与用量，不包含编排状态。"""

    text: str
    model_id: str
    input_tokens: int
    output_tokens: int


class ModelPort(Protocol):
    """Harness 调用基座模型时依赖的异步接口。"""

    async def generate(
        self, messages: list[dict[str, str]]
    ) -> ModelResponse:
        """根据消息生成一次模型响应。"""
        ...
