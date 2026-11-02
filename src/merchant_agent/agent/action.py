"""将规划结果分派给 MCP 工具，并把观察结果写回 Agent State。"""

import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import asdict

from merchant_agent.agent.planning import valid_tool_arguments
from merchant_agent.agent.state import AgentState
from merchant_agent.tools.python_sandbox.failure_classification import classify_python_result
from merchant_agent.tracing.observed_python import execute_python_observed
from merchant_agent.tracing.observed_search import search_web_observed
from merchant_agent.tracing.observed_sql import call_store_net_observed
from merchant_agent.tracing.tool_failure import ObservedToolFailure


def make_tool_node(client, trace_path: str) -> Callable[[AgentState], Awaitable[dict]]:
    """注入 MCP 客户端和 Trace 路径，返回一次工具行动节点。"""
    async def tool_node(state: AgentState) -> dict:
        name = state["selected_tool"]
        arguments = state["tool_arguments"]
        if not isinstance(name, str) or not valid_tool_arguments(name, arguments):
            raise ValueError("行动节点收到无效工具或参数")

        # operation_id 跨同一逻辑操作的重试保持不变，每次实际调用递增 attempt。
        operation_id = state["operation_id"]
        if not operation_id:
            raise ValueError("行动节点缺少 operation_id")
        attempt = state["tool_attempt"] + 1
        common = dict(
            trace_path=trace_path,
            trace_id=state["trace_id"],
            parent_span_id=state["root_span_id"],
            operation_id=operation_id,
            attempt=attempt,
        )
        try:
            if name == "get_store_net":
                value = await call_store_net_observed(client, arguments["store_id"], **common)
                observation = {
                    "tool_name": name,
                    "outcome": "empty_result" if value is None else "success",
                    "result_fen": value,
                }
            elif name == "search_web":
                snapshot = await search_web_observed(
                    client, arguments["query"], arguments["limit"], **common
                )
                observation = {
                    "tool_name": name,
                    "outcome": "empty_result" if not snapshot["results"] else "success",
                    "snapshot": snapshot,
                }
            else:
                result = await execute_python_observed(
                    client, arguments["code"], arguments["timeout_seconds"], **common
                )
                observation = {
                    "tool_name": name,
                    "outcome": classify_python_result(result),
                    "result": asdict(result),
                }
        except ObservedToolFailure as exc:
            # 只有观测包装明确标记的故障才能转成观察；写盘错误不会进入这里。
            observation = {"tool_name": name, "outcome": exc.outcome,
                           "raw_status": exc.raw_status}
        except asyncio.TimeoutError:
            observation = {"tool_name": name, "outcome": "timeout", "raw_status": "timeout"}
        return {
            "operation_id": operation_id,
            "tool_attempt": attempt,
            "last_tool_result": observation,
            "messages": [{"role": "tool", "content": json.dumps(observation, ensure_ascii=False)}],
            "step_count": 1,
        }

    return tool_node
