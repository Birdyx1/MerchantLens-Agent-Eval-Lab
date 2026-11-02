"""组装单轮与有界观察循环的 LangGraph 图。"""

from collections.abc import Awaitable, Callable

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from merchant_agent.agent.model_port import ModelPort
from merchant_agent.agent.planning import make_plan_node, route_after_plan
from merchant_agent.agent.retry_policy import should_retry_tool
from merchant_agent.agent.state import AgentState


def build_single_turn_graph(
    model: ModelPort,
    tool_node: Callable[[AgentState], Awaitable[dict]],
    *,
    trace_path: str | None = None,
):
    """注入模型和工具节点，编译一轮“规划→可选行动”的图。"""
    graph = StateGraph(AgentState)
    graph.add_node("plan", make_plan_node(model, trace_path))
    graph.add_node("act", tool_node)
    graph.add_edge(START, "plan")
    # 结束决策直接退出；工具决策进入注入的行动节点。
    graph.add_conditional_edges("plan", route_after_plan, {"tool": "act", "finish": END})
    graph.add_edge("act", END)
    return graph.compile()


def _route_plan_with_budget(state: AgentState) -> str:
    """规划后检查 token 与步骤预算，不让超预算动作继续。"""
    choice = route_after_plan(state)
    if state["input_tokens"] + state["output_tokens"] >= state["max_total_tokens"]:
        return "tokens"
    if choice == "tool" and state["step_count"] >= state["max_steps"]:
        return "budget"
    return choice


def _route_after_action(state: AgentState) -> str:
    """预算不足则终止；明确超时可原参数重试，其余返回规划。"""
    if state["input_tokens"] + state["output_tokens"] >= state["max_total_tokens"]:
        return "tokens"
    if state["step_count"] >= state["max_steps"]:
        return "budget"
    return "retry" if should_retry_tool(state) else "continue"


def _retry_node(state: AgentState) -> dict:
    """记录一次确定性重试决策；工具节点负责实际调用和新 Span。"""
    return {"retry_count": 1}


def _budget_node(state: AgentState) -> dict:
    """预算耗尽时不给出虚构答案，保留终止原因供评测读取。"""
    return {
        "selected_tool": None,
        "tool_arguments": None,
        "final_answer": None,
        "termination_reason": "max_steps",
    }


def _token_budget_node(state: AgentState) -> dict:
    """token 预算耗尽时记录原因，不把超预算模型文本当作最终答案。"""
    return {
        "selected_tool": None,
        "tool_arguments": None,
        "final_answer": None,
        "termination_reason": "max_tokens",
    }


def build_observation_loop_graph(
    model: ModelPort,
    tool_node: Callable[[AgentState], Awaitable[dict]],
    *,
    checkpointer: BaseCheckpointSaver | None = None,
    interrupt_before: list[str] | None = None,
    trace_path: str | None = None,
):
    """编译有界循环图；可注入检查点并在指定节点前暂停。"""
    graph = StateGraph(AgentState)
    graph.add_node("plan", make_plan_node(model, trace_path))
    graph.add_node("act", tool_node)
    graph.add_node("retry", _retry_node)
    graph.add_node("budget", _budget_node)
    graph.add_node("tokens", _token_budget_node)
    graph.add_edge(START, "plan")
    graph.add_conditional_edges(
        "plan", _route_plan_with_budget,
        {"tool": "act", "finish": END, "budget": "budget", "tokens": "tokens"},
    )
    graph.add_conditional_edges(
        "act", _route_after_action,
        {"continue": "plan", "retry": "retry", "budget": "budget", "tokens": "tokens"},
    )
    graph.add_edge("retry", "act")
    graph.add_edge("budget", END)
    graph.add_edge("tokens", END)
    return graph.compile(checkpointer=checkpointer, interrupt_before=interrupt_before)
