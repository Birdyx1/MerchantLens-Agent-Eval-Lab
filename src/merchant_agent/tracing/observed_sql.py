"""为 MCP SQL 工具调用生成单次尝试的结构化 Trace。"""

import asyncio
import time
import uuid
from datetime import datetime, timezone

from merchant_agent.tracing.tool_attempt import ToolAttempt
from merchant_agent.tracing.tool_failure import ObservedToolFailure
from merchant_agent.tracing.writer import append_span


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def call_store_net_observed(
    client,
    store_id: str,
    *,
    trace_path: str,
    trace_id: str,
    parent_span_id: str,
    operation_id: str,
    attempt: int = 1,
) -> int | None:
    """调用一次 SQL 工具并落盘；调用失败时仍记录 Span 后传播异常。"""
    if isinstance(attempt, bool) or not isinstance(attempt, int) or attempt < 1:
        raise ValueError("attempt 必须是从 1 开始的整数")
    if not operation_id:
        raise ValueError("operation_id 不能为空")
    started_at = _utc_now()
    started = time.monotonic()
    raw_status = "not_started"
    outcome = "dependency_error"
    result_fen = None
    error_type = None
    try:
        response = await client.call_tool("get_store_net", {"store_id": store_id})
        if response.is_error:
            raw_status = "mcp_error"
            raise ObservedToolFailure("get_store_net 工具调用失败", raw_status=raw_status)
        content = response.structured_content
        if not isinstance(content, dict) or "result" not in content:
            raw_status = "protocol_error"
            raise ObservedToolFailure("get_store_net 缺少结构化结果", raw_status=raw_status)
        value = content["result"]
        if value is not None and (isinstance(value, bool) or not isinstance(value, int)):
            raw_status = "protocol_error"
            raise ObservedToolFailure("get_store_net 返回值类型无效", raw_status=raw_status)
        result_fen = value
        raw_status = "ok"
        outcome = "empty_result" if value is None else "success"
        return value
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
            tool_name="get_store_net",
            operation_id=operation_id,
            attempt=attempt,
            raw_status=raw_status,
            outcome=outcome,
            start_time=started_at,
            end_time=_utc_now(),
            duration_ms=int((time.monotonic() - started) * 1000),
        ).to_span()
        span["attributes"]["store_id"] = store_id
        if outcome in {"success", "empty_result"}:
            span["attributes"]["result_fen"] = result_fen
        if error_type is not None:
            span["attributes"]["error_type"] = error_type
        append_span(trace_path, span)
