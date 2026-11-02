"""测试辅助进程：在 SQLite 检查点前暂停，并在新进程恢复。"""

import asyncio
import json
import sys

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from mcp import Client

from merchant_agent.agent.action import make_tool_node
from merchant_agent.agent.graph import build_observation_loop_graph
from merchant_agent.agent.model_port import ModelResponse
from merchant_agent.agent.state import initial_state
from merchant_agent.mcp_server import create_server


class CheckpointModel:
    """按 State 中是否已有工具观察决定调用 SQL 或结束。"""

    async def generate(self, messages):
        observations = [item for item in messages if item["role"] == "tool"]
        if observations:
            amount = json.loads(observations[-1]["content"])["result_fen"]
            action = {"type": "finish", "answer": f"门店 A 净收入为 {amount} 分"}
        else:
            action = {"type": "tool", "name": "get_store_net", "arguments": {"store_id": "A"}}
        text = json.dumps({"plan": ["查询并核对 SQL"], "action": action})
        return ModelResponse(text, "checkpoint-model", 5, 3)


async def run(mode: str, checkpoint_path: str, db_path: str, trace_path: str) -> dict:
    config = {"configurable": {"thread_id": "checkpoint-task"}}
    async with AsyncSqliteSaver.from_conn_string(checkpoint_path) as saver:
        async with Client(create_server(db_path)) as client:
            graph = build_observation_loop_graph(
                CheckpointModel(), make_tool_node(client, trace_path),
                checkpointer=saver,
                interrupt_before=["act"] if mode == "write" else None,
            )
            if mode == "write":
                await graph.ainvoke(initial_state(
                    "task-1", "a" * 32, "b" * 16, "门店 A 净收入？"
                ), config)
            elif mode == "resume":
                await graph.ainvoke(None, config)
            else:
                raise ValueError("未知测试模式")
            snapshot = await graph.aget_state(config)
            return {
                "next": list(snapshot.next),
                "final_answer": snapshot.values["final_answer"],
                "step_count": snapshot.values["step_count"],
                "trace_id": snapshot.values["trace_id"],
            }


if __name__ == "__main__":
    print(json.dumps(asyncio.run(run(*sys.argv[1:]))))
