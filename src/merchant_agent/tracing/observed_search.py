"""为 MCP 搜索工具调用记录证据快照和单次尝试 Trace。"""

import asyncio
import time
import uuid
from datetime import datetime, timezone

from merchant_agent.tracing.tool_attempt import ToolAttempt
from merchant_agent.tracing.tool_failure import ObservedToolFailure
from merchant_agent.tracing.writer import append_span


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def search_web_observed(
    client,
    query: str,
    limit: int,
    *,
    trace_path: str,
    trace_id: str,
    parent_span_id: str,
    operation_id: str,
    attempt: int = 1,
) -> dict:
    """调用一次 MCP 搜索，返回结构化快照并将本次尝试写入 Trace。"""
    if isinstance(attempt, bool) or not isinstance(attempt, int) or attempt < 1:
        raise ValueError("attempt 必须是从 1 开始的整数")
    if not operation_id:
        raise ValueError("operation_id 不能为空")

    started_at = _utc_now()
    started = time.monotonic()
    raw_status = "not_started"
    outcome = "dependency_error"
    snapshot = None
    error_type = None
    try:
        response = await client.call_tool("search_web", {"query": query, "limit": limit})
        if response.is_error:
            raw_status = "mcp_error"
            raise ObservedToolFailure("search_web 工具调用失败", raw_status=raw_status)
        content = response.structured_content
        if (not isinstance(content, dict) or content.get("query") != query
                or not isinstance(content.get("results"), list)
                or any(not isinstance(item, dict) for item in content["results"])):
            raw_status = "protocol_error"
            raise ObservedToolFailure("search_web 结构化结果无效", raw_status=raw_status)
        snapshot = content
        raw_status = "ok"
        outcome = "empty_result" if not content["results"] else "success"
        return content
    except asyncio.TimeoutError:
        raw_status = "timeout"
        outcome = "timeout"
        error_type = "TimeoutError"
        raise
    except Exception as exc:
        error_type = type(exc).__name__
        if raw_status == "not_started":
            raw_status = "client_exception"
        raise
    finally:
        span = ToolAttempt(
            trace_id=trace_id,
            span_id=uuid.uuid4().hex[:16],
            parent_span_id=parent_span_id,
            tool_name="search_web",
            operation_id=operation_id,
            attempt=attempt,
            raw_status=raw_status,
            outcome=outcome,
            start_time=started_at,
            end_time=_utc_now(),
            duration_ms=int((time.monotonic() - started) * 1000),
        ).to_span()
        span["attributes"]["arguments"] = {"query": query, "limit": limit}
        if snapshot is not None:
            span["attributes"]["search_snapshot"] = snapshot
        if error_type is not None:
            span["attributes"]["error_type"] = error_type
        append_span(trace_path, span)
