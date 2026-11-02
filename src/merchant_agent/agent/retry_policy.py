"""决定工具观察是否可以原参数有限重试。"""

from merchant_agent.agent.state import AgentState


READ_ONLY_TOOLS = frozenset({"get_store_net", "search_web"})


def should_retry_tool(state: AgentState) -> bool:
    """仅对只读工具的明确调用超时，且仍有次数和步骤预算时重试。"""
    observation = state["last_tool_result"]
    if not isinstance(observation, dict):
        return False
    return (
        state["selected_tool"] in READ_ONLY_TOOLS
        and observation.get("tool_name") == state["selected_tool"]
        and observation.get("outcome") == "timeout"
        and observation.get("raw_status") == "timeout"
        and state["operation_id"] is not None
        and state["tool_attempt"] < state["max_tool_attempts"]
        and state["step_count"] < state["max_steps"]
    )
