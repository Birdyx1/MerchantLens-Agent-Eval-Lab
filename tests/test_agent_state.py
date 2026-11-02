import pytest
from langgraph.graph import END, START, StateGraph

from merchant_agent.agent.state import AgentState, initial_state


def test_initial_state_has_trace_and_budget():
    state = initial_state("task-1", "a" * 32, "b" * 16, "门店 A 的净收入？", max_steps=5)
    assert state["messages"] == [{"role": "user", "content": "门店 A 的净收入？"}]
    assert state["trace_id"] == "a" * 32
    assert state["root_span_id"] == "b" * 16
    assert state["step_count"] == state["retry_count"] == 0
    assert state["max_steps"] == 5
    assert state["final_answer"] is None


def test_langgraph_applies_incremental_updates():
    def plan_node(state: AgentState) -> dict:
        assert state["user_request"] == "门店 A 的净收入？"
        return {
            "plan": ["查询 SQL", "核对金额"],
            "messages": [{"role": "assistant", "content": "先查询 SQL"}],
            "step_count": 1,
            "input_tokens": 12,
            "output_tokens": 5,
        }

    graph = StateGraph(AgentState)
    graph.add_node("plan", plan_node)
    graph.add_edge(START, "plan")
    graph.add_edge("plan", END)
    result = graph.compile().invoke(initial_state("task-1", "a" * 32, "b" * 16, "门店 A 的净收入？"))
    assert result["plan"] == ["查询 SQL", "核对金额"]
    assert len(result["messages"]) == 2
    assert result["step_count"] == 1
    assert (result["input_tokens"], result["output_tokens"]) == (12, 5)


@pytest.mark.parametrize("user_text, max_steps", [("  ", 8), ("正常请求", 0), ("正常请求", True)])
def test_invalid_initial_state_rejected(user_text, max_steps):
    with pytest.raises(ValueError):
        initial_state("task-1", "a" * 32, "b" * 16, user_text, max_steps=max_steps)
