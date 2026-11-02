import asyncio
import json

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from merchant_agent.agent.graph import build_observation_loop_graph
from merchant_agent.agent.model_port import ModelResponse
from merchant_agent.agent.state import initial_state


class EchoFinishModel:
    async def generate(self, messages):
        user_text = next(message["content"] for message in messages if message["role"] == "user")
        text = json.dumps({"plan": [], "action": {"type": "finish", "answer": f"收到：{user_text}"}})
        return ModelResponse(text, "echo-model", 3, 2)


async def unused_tool_node(state):
    raise AssertionError("直接结束的决策不应进入工具节点")


def test_checkpointer_isolates_task_threads_and_keeps_history():
    graph = build_observation_loop_graph(
        EchoFinishModel(), unused_tool_node, checkpointer=InMemorySaver()
    )
    config_a = {"configurable": {"thread_id": "task-a"}}
    config_b = {"configurable": {"thread_id": "task-b"}}

    async def run():
        await graph.ainvoke(initial_state("task-a", "a" * 32, "b" * 16, "查询 A"), config_a)
        await graph.ainvoke(initial_state("task-b", "c" * 32, "d" * 16, "查询 B"), config_b)
        snapshot_a = await graph.aget_state(config_a)
        snapshot_b = await graph.aget_state(config_b)
        history_a = [item async for item in graph.aget_state_history(config_a)]
        return snapshot_a, snapshot_b, history_a

    snapshot_a, snapshot_b, history_a = asyncio.run(run())
    assert snapshot_a.values["final_answer"] == "收到：查询 A"
    assert snapshot_b.values["final_answer"] == "收到：查询 B"
    assert snapshot_a.values["trace_id"] == "a" * 32
    assert snapshot_b.values["trace_id"] == "c" * 32
    assert len(history_a) >= 2
    assert all(item.config["configurable"]["thread_id"] == "task-a" for item in history_a)


def test_checkpointed_graph_requires_thread_id():
    graph = build_observation_loop_graph(
        EchoFinishModel(), unused_tool_node, checkpointer=InMemorySaver()
    )
    with pytest.raises(ValueError, match="thread_id"):
        asyncio.run(graph.ainvoke(initial_state("task-a", "a" * 32, "b" * 16, "查询 A")))
