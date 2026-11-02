"""按项目预算配置调用已编译的 LangGraph 图。"""

import asyncio
import math
import time
from datetime import datetime, timezone

from merchant_agent.agent.state import AgentState
from merchant_agent.tracing.writer import append_span


class AgentDeadlineExceeded(TimeoutError):
    """单次 Agent 调用超过墙钟时限；调用方应将其记录为未完成。"""

    reason = "deadline"


async def run_agent(
    graph,
    state: AgentState,
    *,
    thread_id: str | None = None,
    timeout_seconds: float | None = None,
    trace_path: str | None = None,
) -> AgentState:
    """执行一次图调用，并可记录本次调用的根 Span。"""
    if timeout_seconds is not None and (
        isinstance(timeout_seconds, bool)
        or not isinstance(timeout_seconds, (int, float))
        or not math.isfinite(timeout_seconds)
        or timeout_seconds <= 0
    ):
        raise ValueError("timeout_seconds 必须是有限正数")
    config = {"recursion_limit": 3 * state["max_steps"] + 10}
    if thread_id is not None:
        if not thread_id.strip():
            raise ValueError("thread_id 不能为空")
        config["configurable"] = {"thread_id": thread_id}
    started_at = datetime.now(timezone.utc).isoformat()
    started = time.monotonic()
    reason = "error"
    error_type = None
    try:
        if timeout_seconds is None:
            result = await graph.ainvoke(state, config)
        else:
            deadline = asyncio.timeout(timeout_seconds)
            try:
                async with deadline:
                    result = await graph.ainvoke(state, config)
            except TimeoutError as exc:
                # 只把本层时限触发的超时归为 Agent deadline。
                if deadline.expired():
                    raise AgentDeadlineExceeded("Agent 调用超过墙钟时限") from exc
                raise
        reason = result.get("termination_reason") or "interrupted"
        return result
    except AgentDeadlineExceeded:
        reason = "deadline"
        error_type = "AgentDeadlineExceeded"
        raise
    except asyncio.CancelledError:
        reason = "cancelled"
        error_type = "CancelledError"
        raise
    except Exception as exc:
        error_type = type(exc).__name__
        raise
    finally:
        if trace_path is not None:
            # 根 Span 在结束时追加，因此工具 Span 可以先写盘再关联根 ID。
            attributes = {
                "task_id": state["task_id"],
                "termination_reason": reason,
                "duration_ms": int((time.monotonic() - started) * 1000),
            }
            if error_type is not None:
                attributes["error_type"] = error_type
            append_span(trace_path, {
                "trace_id": state["trace_id"],
                "span_id": state["root_span_id"],
                "parent_span_id": None,
                "name": "agent.request",
                "start_time": started_at,
                "end_time": datetime.now(timezone.utc).isoformat(),
                "attributes": attributes,
            })
