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
    "当前日期：2026-11-03。"
    "格式：{\"plan\":[\"简短步骤\"],\"action\":{\"type\":\"tool\","
    "\"name\":\"工具名\",\"arguments\":{...}}}；"
    "若已能回答，action 使用 {\"type\":\"finish\",\"answer\":\"答案\"}。"
    "可用 run_sql(query) 执行只读 SELECT/WITH 查询；数据库表："
    "orders(order_id,store_id,order_date,category,channel,paid_fen,refunded_fen)、"
    "stores(store_id,store_name,region,city)。"
    "门店指标工具 get_store_net/get_store_paid_total/get_store_refunded_total/"
    "get_store_order_count/get_store_refunded_order_count/get_store_refund_rate/"
    "get_store_aov 接受 store_id。"
    "另有 search_web(query,limit) 与 execute_python(code,timeout_seconds)。"
    "plan 只写可执行步骤摘要，不输出隐藏推理。"
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


STORE_ID_TOOLS = frozenset({
    "get_store_net", "get_store_order_count", "get_store_refund_rate", "get_store_aov",
    "get_store_paid_total", "get_store_refunded_total", "get_store_refunded_order_count",
})


def valid_tool_arguments(name: str, arguments: object) -> bool:
    """按工具公开参数契约校验，不让模型选择部署配置。"""
    if not isinstance(arguments, dict):
        return False
    if name in STORE_ID_TOOLS:
        return (set(arguments) == {"store_id"}
                and isinstance(arguments["store_id"], str)
                and bool(arguments["store_id"].strip()))
    if name == "run_sql":
        return (set(arguments) == {"query"}
                and isinstance(arguments["query"], str)
                and bool(arguments["query"].strip())
                and len(arguments["query"]) <= 2000)
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


_ANSWER_MARKERS = ("|", "分", "%", "合计", "净收入", "退款率", "订单", "。")
_ANSWER_MIN_LENGTH = 10


def _looks_like_answer(text: str) -> bool:
    """粗判纯文本是否像最终答案；用于把模型的自然语言收尾容错为 finish，而非误收错误输出。"""
    return len(text) >= _ANSWER_MIN_LENGTH and any(marker in text for marker in _ANSWER_MARKERS)


def parse_planning_decision(text: str) -> PlanningDecision:
    """解析规划决策；像答案的纯文本容错为最终答案，其余拒绝。"""
    stripped = text.strip() if isinstance(text, str) else ""
    try:
        data = json.loads(text)
    except (TypeError, json.JSONDecodeError):
        # Markdown 代码块或坏 JSON、以及不像答案的短文本一律拒绝；
        # 只有像答案的纯文本才视为模型直接给出的自然语言答案。
        if stripped.startswith("```") or stripped.startswith("{"):
            raise ValueError("规划输出不是合法 JSON") from None
        if _looks_like_answer(stripped):
            return PlanningDecision(plan=[], tool_name=None, tool_arguments=None,
                                    final_answer=stripped)
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


def make_plan_node(model: ModelPort, trace_path: str | None = None, *,
                   planning_instruction: str = PLANNING_INSTRUCTION) -> Callable[[AgentState], Awaitable[dict]]:
    """注入模型适配器，返回只负责一次规划的异步节点。"""
    if not planning_instruction.strip():
        raise ValueError("规划指令不能为空")
    async def plan_node(state: AgentState) -> dict:
        instructions = [{"role": "system", "content": planning_instruction}]
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
