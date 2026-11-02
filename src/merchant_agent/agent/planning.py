"""解析模型规划决策，并生成 LangGraph 规划节点与路由函数。"""

import json
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from merchant_agent.agent.model_port import ModelPort
from merchant_agent.agent.state import AgentState
from merchant_agent.tracing.writer import append_span


PLANNING_INSTRUCTION = (
    "你是商家经营分析 Agent 的规划器。只返回一个 JSON 对象，不要 Markdown。"
    "格式：{\"plan\":[\"简短步骤\"],\"action\":{\"type\":\"tool\","
    "\"name\":\"工具名\",\"arguments\":{...}}}；"
    "若已能回答，action 使用 {\"type\":\"finish\",\"answer\":\"答案\"}。"
    "工具仅有 get_store_net(store_id)、search_web(query,limit)、"
    "execute_python(code,timeout_seconds)。plan 只写可执行步骤摘要，不输出隐藏推理。"
)

REFLECTION_INSTRUCTION = (
    "上一次工具调用失败。检查已有失败观察，不要假设失败工具返回了有效数据。"
    "可修正参数、改用其他工具，或说明无法可靠完成并结束。"
    "不得原样重复同一工具和参数，也不得绕过安全拒绝。"
)

FAILURE_OUTCOMES = frozenset({
    "invalid_input", "timeout", "dependency_error", "program_error", "security_rejected",
})


@dataclass(frozen=True, slots=True)
class PlanningDecision:
    """经确定性校验后的单次规划结果。"""

    plan: list[str]
    tool_name: str | None
    tool_arguments: dict[str, object] | None
    final_answer: str | None


def valid_tool_arguments(name: str, arguments: object) -> bool:
    """按工具公开参数契约校验，不让模型选择部署配置。"""
    if not isinstance(arguments, dict):
        return False
    if name == "get_store_net":
        return (set(arguments) == {"store_id"}
                and isinstance(arguments["store_id"], str)
                and bool(arguments["store_id"].strip()))
    if name == "search_web":
        return (set(arguments) == {"query", "limit"}
                and isinstance(arguments["query"], str)
                and bool(arguments["query"].strip())
                and type(arguments["limit"]) is int
                and 1 <= arguments["limit"] <= 10)
    if name == "execute_python":
        return (set(arguments) == {"code", "timeout_seconds"}
                and isinstance(arguments["code"], str)
                and bool(arguments["code"].strip())
                and type(arguments["timeout_seconds"]) is int
                and 1 <= arguments["timeout_seconds"] <= 5)
    return False


def parse_planning_decision(text: str) -> PlanningDecision:
    """只接受约定 JSON；无效决策不能进入工具执行节点。"""
    try:
        data = json.loads(text)
    except (TypeError, json.JSONDecodeError):
        raise ValueError("规划输出不是合法 JSON") from None
    if not isinstance(data, dict) or set(data) != {"plan", "action"}:
        raise ValueError("规划输出顶层结构无效")
    plan = data["plan"]
    if (not isinstance(plan, list) or len(plan) > 5
            or any(not isinstance(item, str) or not item.strip() or len(item) > 200 for item in plan)):
        raise ValueError("plan 必须是至多五条非空短步骤")
    action = data["action"]
    if not isinstance(action, dict):
        raise ValueError("action 必须是对象")
    if action.get("type") == "tool":
        if set(action) != {"type", "name", "arguments"}:
            raise ValueError("工具 action 字段无效")
        name = action["name"]
        arguments = action["arguments"]
        if not isinstance(name, str) or not valid_tool_arguments(name, arguments):
            raise ValueError("工具名或工具参数无效")
        return PlanningDecision(plan, name, arguments, None)
    if action.get("type") == "finish":
        if (set(action) != {"type", "answer"} or not isinstance(action["answer"], str)
                or not action["answer"].strip()):
            raise ValueError("最终答案 action 无效")
        return PlanningDecision(plan, None, None, action["answer"])
    raise ValueError("未知规划 action 类型")


def validate_reflection_decision(state: AgentState, decision: PlanningDecision) -> None:
    """禁止失败后的原样重复调用，以及安全拒绝后的继续调用。"""
    observation = state["last_tool_result"]
    if not isinstance(observation, dict) or observation.get("outcome") not in FAILURE_OUTCOMES:
        return
    if observation["outcome"] == "security_rejected" and decision.tool_name is not None:
        raise ValueError("安全拒绝后不能继续调用工具")
    if (decision.tool_name is not None
            and decision.tool_name == state["selected_tool"]
            and decision.tool_arguments == state["tool_arguments"]):
        raise ValueError("失败后不能原样重复同一工具调用")


def make_plan_node(model: ModelPort, trace_path: str | None = None) -> Callable[[AgentState], Awaitable[dict]]:
    """注入模型适配器，返回只负责一次规划的异步节点。"""
    async def plan_node(state: AgentState) -> dict:
        instructions = [{"role": "system", "content": PLANNING_INSTRUCTION}]
        observation = state["last_tool_result"]
        if isinstance(observation, dict) and observation.get("outcome") in FAILURE_OUTCOMES:
            instructions.append({"role": "system", "content": REFLECTION_INSTRUCTION})
        messages = [*instructions, *state["messages"]]
        started_at = datetime.now(timezone.utc).isoformat()
        started = time.monotonic()
        attributes: dict[str, object] = {"outcome": "error"}
        try:
            response = await model.generate(messages)
            attributes["model_output"] = response.text
            attributes["model_id"] = response.model_id
            attributes["input_tokens"] = response.input_tokens
            attributes["output_tokens"] = response.output_tokens
            decision = parse_planning_decision(response.text)
            validate_reflection_decision(state, decision)
            if (not isinstance(response.model_id, str) or not response.model_id.strip()
                    or type(response.input_tokens) is not int
                    or type(response.output_tokens) is not int
                    or response.input_tokens < 0 or response.output_tokens < 0):
                raise ValueError("模型返回的版本或 token 用量无效")
            attributes.update({
                "outcome": "success",
                "plan": decision.plan,
                "selected_tool": decision.tool_name,
                "tool_arguments": decision.tool_arguments,
                "action_type": "finish" if decision.final_answer is not None else "tool",
            })
        except BaseException as exc:
            # 取消也要留下 Span；原异常仍由调用方处理。
            attributes["error_type"] = type(exc).__name__
            raise
        finally:
            if trace_path is not None:
                attributes["duration_ms"] = int((time.monotonic() - started) * 1000)
                append_span(trace_path, {
                    "trace_id": state["trace_id"],
                    "span_id": uuid.uuid4().hex[:16],
                    "parent_span_id": state["root_span_id"],
                    "name": "model.plan",
                    "start_time": started_at,
                    "end_time": datetime.now(timezone.utc).isoformat(),
                    "attributes": attributes,
                })
        return {
            "plan": decision.plan,
            "selected_tool": decision.tool_name,
            "tool_arguments": decision.tool_arguments,
            # 先把逻辑操作 ID 写入 State，工具失败后仍可关联同一操作的后续尝试。
            "operation_id": (uuid.uuid4().hex if decision.tool_name is not None
                             else state["operation_id"]),
            "tool_attempt": 0 if decision.tool_name is not None else state["tool_attempt"],
            "final_answer": decision.final_answer,
            "termination_reason": "completed" if decision.final_answer is not None else None,
            "last_model_id": response.model_id,
            "messages": [{"role": "assistant", "content": response.text}],
            "step_count": 1,
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
        }

    return plan_node


def route_after_plan(state: AgentState) -> str:
    """根据已校验的状态选择工具节点或结束分支。"""
    if (state["final_answer"] is None) == (state["selected_tool"] is None):
        raise ValueError("规划状态必须且只能选择工具或最终答案")
    if state["final_answer"] is not None:
        return "finish"
    return "tool"
