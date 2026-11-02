"""LangGraph Agent 的短期共享状态与初始状态工厂。"""

import operator
from typing import Annotated, TypedDict


class AgentState(TypedDict):
    """节点间共享的短期状态；节点只需返回本次修改的字段。"""

    # 运行身份与 Trace 关联由入口创建，节点不应自行更换。
    task_id: str
    trace_id: str
    root_span_id: str

    # 保留原始请求；提示词应在节点内按需构造，不存进 State。
    user_request: str
    # operator.add 会把节点返回的新消息追加到现有列表，不能返回完整历史。
    messages: Annotated[list[dict[str, str]], operator.add]

    # 以下业务字段没有 reducer，节点返回新值时会覆盖旧值。
    plan: list[str]
    selected_tool: str | None
    tool_arguments: dict[str, object] | None
    operation_id: str | None
    tool_attempt: int
    last_tool_result: dict[str, object] | None
    final_answer: str | None
    termination_reason: str | None
    last_model_id: str | None

    # 节点返回的是本次增量，例如 step_count=1，而不是累计总数。
    step_count: Annotated[int, operator.add]
    retry_count: Annotated[int, operator.add]
    input_tokens: Annotated[int, operator.add]
    output_tokens: Annotated[int, operator.add]
    # 预算值由入口设定；路由节点在每一步后判断是否需要终止。
    max_steps: int
    max_tool_attempts: int
    # 当前模型调用结束后才知道实际用量，因此这是事后停止阈值。
    max_total_tokens: int


def initial_state(
    task_id: str,
    trace_id: str,
    root_span_id: str,
    user_request: str,
    *,
    max_steps: int = 8,
    max_tool_attempts: int = 2,
    max_total_tokens: int = 4096,
) -> AgentState:
    """构造一次 Agent 运行的初始状态，不执行模型或工具。"""
    # 在调用图之前拒绝无效入口数据，避免节点运行到一半才发现缺字段。
    if not task_id.strip() or not user_request.strip():
        raise ValueError("task_id 和 user_request 不能为空")
    if not trace_id or not root_span_id:
        raise ValueError("Trace ID 和根 Span ID 不能为空")
    if isinstance(max_steps, bool) or not isinstance(max_steps, int) or max_steps < 1:
        raise ValueError("max_steps 必须是正整数")
    if (isinstance(max_tool_attempts, bool) or not isinstance(max_tool_attempts, int)
            or not 1 <= max_tool_attempts <= 3):
        raise ValueError("max_tool_attempts 必须是 1 到 3 的整数")
    if (isinstance(max_total_tokens, bool) or not isinstance(max_total_tokens, int)
            or max_total_tokens < 1):
        raise ValueError("max_total_tokens 必须是正整数")
    # 显式填齐字段，让后续节点能够直接读取，不依赖缺省键的隐式约定。
    return AgentState(
        task_id=task_id,
        trace_id=trace_id,
        root_span_id=root_span_id,
        user_request=user_request,
        messages=[{"role": "user", "content": user_request}],
        plan=[],
        selected_tool=None,
        tool_arguments=None,
        operation_id=None,
        tool_attempt=0,
        last_tool_result=None,
        final_answer=None,
        termination_reason=None,
        last_model_id=None,
        step_count=0,
        retry_count=0,
        input_tokens=0,
        output_tokens=0,
        max_steps=max_steps,
        max_tool_attempts=max_tool_attempts,
        max_total_tokens=max_total_tokens,
    )
