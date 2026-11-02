"""将单次工具调用的观测结果转换为项目 Trace Span。"""

from dataclasses import dataclass


OUTCOMES = frozenset({
    "success", "empty_result", "invalid_input", "timeout",
    "dependency_error", "program_error", "security_rejected",
})


@dataclass(frozen=True)
class ToolAttempt:
    trace_id: str
    span_id: str
    parent_span_id: str
    tool_name: str
    operation_id: str
    attempt: int
    raw_status: str
    outcome: str
    start_time: str
    end_time: str
    duration_ms: int

    def __post_init__(self) -> None:
        if not self.tool_name or not self.operation_id or not self.raw_status:
            raise ValueError("工具名、操作 ID 和原始状态不能为空")
        if isinstance(self.attempt, bool) or not isinstance(self.attempt, int) or self.attempt < 1:
            raise ValueError("attempt 必须是从 1 开始的整数")
        if isinstance(self.duration_ms, bool) or not isinstance(self.duration_ms, int) or self.duration_ms < 0:
            raise ValueError("duration_ms 必须是非负整数")
        if self.outcome not in OUTCOMES:
            raise ValueError("未知工具评测类别")

    def to_span(self) -> dict:
        """生成符合当前 Span 字段布局的字典，不执行写盘。"""
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "name": f"tool.{self.tool_name}",
            "start_time": self.start_time,
            "end_time": self.end_time,
            "attributes": {
                "operation_id": self.operation_id,
                "attempt": self.attempt,
                "raw_status": self.raw_status,
                "outcome": self.outcome,
                "duration_ms": self.duration_ms,
            },
        }
