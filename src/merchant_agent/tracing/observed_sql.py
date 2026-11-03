"""为 MCP SQL 工具调用生成单次尝试的结构化 Trace。"""

import asyncio
import json
import time
import uuid
from datetime import datetime, timezone

from merchant_agent.tracing.tool_attempt import OUTCOMES, ToolAttempt
from merchant_agent.tracing.tool_failure import ObservedToolFailure
from merchant_agent.tracing.writer import append_span


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_run_sql_result(response) -> dict | None:
    """兼容 MCP 对 dict 返回的两种呈现：structured_content 或 content text 里的 JSON。"""
    content = getattr(response, "structured_content", None)
    if isinstance(content, dict):
        candidate = content.get("result", content)
        if isinstance(candidate, dict):
            return candidate
    for item in getattr(response, "content", None) or []:
        text = getattr(item, "text", None)
        if not text:
            continue
        try:
            parsed = json.loads(text)
        except (TypeError, ValueError):
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


async def call_sql_tool_observed(
    client,
    tool_name: str,
    arguments: dict[str, object],
    *,
    result_field: str,
    allowed_types: tuple[type, ...] = (int,),
    trace_path: str,
    trace_id: str,
    parent_span_id: str,
    operation_id: str,
    attempt: int = 1,
):
    """调用一次 SQL 工具并落盘；调用失败时仍记录 Span 后传播异常。

    result_field 决定把返回值写进 Span 的哪个属性（如 result_fen / result_count /
    result_rate），allowed_types 校验返回值类型，避免协议漂移被静默接受。
    """
    if isinstance(attempt, bool) or not isinstance(attempt, int) or attempt < 1:
        raise ValueError("attempt 必须是从 1 开始的整数")
    if not operation_id:
        raise ValueError("operation_id 不能为空")
    if not isinstance(arguments, dict):
        raise ValueError("工具参数必须是对象")
    started_at = _utc_now()
    started = time.monotonic()
    raw_status = "not_started"
    outcome = "dependency_error"
    result_value = None
    error_type = None
    try:
        response = await client.call_tool(tool_name, arguments)
        if response.is_error:
            raw_status = "mcp_error"
            raise ObservedToolFailure(f"{tool_name} 工具调用失败", raw_status=raw_status)
        content = response.structured_content
        if not isinstance(content, dict) or "result" not in content:
            raw_status = "protocol_error"
            raise ObservedToolFailure(f"{tool_name} 缺少结构化结果", raw_status=raw_status)
        value = content["result"]
        if value is not None and (isinstance(value, bool) or not isinstance(value, allowed_types)):
            raw_status = "protocol_error"
            raise ObservedToolFailure(f"{tool_name} 返回值类型无效", raw_status=raw_status)
        result_value = value
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
            tool_name=tool_name,
            operation_id=operation_id,
            attempt=attempt,
            raw_status=raw_status,
            outcome=outcome,
            start_time=started_at,
            end_time=_utc_now(),
            duration_ms=int((time.monotonic() - started) * 1000),
        ).to_span()
        # 只把工具公开参数写进 Trace，不写部署配置。
        span["attributes"].update(arguments)
        if outcome in {"success", "empty_result"}:
            span["attributes"][result_field] = result_value
        if error_type is not None:
            span["attributes"]["error_type"] = error_type
        append_span(trace_path, span)


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
    """调用一次净收入查询并落盘；保持单门店净收入的既有 Trace 契约。"""
    return await call_sql_tool_observed(
        client, "get_store_net", {"store_id": store_id},
        result_field="result_fen", allowed_types=(int,),
        trace_path=trace_path, trace_id=trace_id, parent_span_id=parent_span_id,
        operation_id=operation_id, attempt=attempt,
    )


async def call_run_sql_observed(
    client,
    query: str,
    *,
    trace_path: str,
    trace_id: str,
    parent_span_id: str,
    operation_id: str,
    attempt: int = 1,
) -> dict:
    """调用一次只读 SQL 工具并落盘；成功记录完整结果集，拒绝记录 outcome。"""
    if not operation_id:
        raise ValueError("operation_id 不能为空")
    if isinstance(attempt, bool) or not isinstance(attempt, int) or attempt < 1:
        raise ValueError("attempt 必须是从 1 开始的整数")
    started_at = _utc_now()
    started = time.monotonic()
    result: dict | None = None
    outcome = "dependency_error"
    raw_status = "not_started"
    error_type = None
    try:
        response = await client.call_tool("run_sql", {"query": query})
        if response.is_error:
            raw_status = "mcp_error"
            raise ObservedToolFailure("run_sql 工具调用失败", raw_status=raw_status)
        result = _extract_run_sql_result(response)
        if result is None:
            raw_status = "protocol_error"
            raise ObservedToolFailure("run_sql 缺少结构化结果", raw_status=raw_status)
        outcome = result.get("outcome", "dependency_error")
        if outcome not in OUTCOMES:
            outcome = "dependency_error"
        raw_status = "ok"
        return result
    except asyncio.TimeoutError:
        raw_status = "timeout"
        outcome = "timeout"
        error_type = "TimeoutError"
        raise
    except ObservedToolFailure:
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
            tool_name="run_sql",
            operation_id=operation_id,
            attempt=attempt,
            raw_status=raw_status,
            outcome=outcome,
            start_time=started_at,
            end_time=_utc_now(),
            duration_ms=int((time.monotonic() - started) * 1000),
        ).to_span()
        # 只记录被截断到 500 字符的查询文本，避免 Trace 过大。
        span["attributes"]["query"] = query[:500]
        if isinstance(result, dict) and result.get("outcome") == "success":
            span["attributes"]["result_set"] = result
        if error_type is not None:
            span["attributes"]["error_type"] = error_type
        append_span(trace_path, span)
