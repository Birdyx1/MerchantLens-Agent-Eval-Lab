"""已记录 Trace 的可预期 MCP 工具故障。"""


class ObservedToolFailure(RuntimeError):
    """工具调用失败且对应尝试 Span 已由观测包装负责落盘。"""

    def __init__(self, message: str, *, raw_status: str) -> None:
        super().__init__(message)
        self.raw_status = raw_status
        self.outcome = "dependency_error"
