"""把单次 Trial 接到真实 LangGraph 与 MCP 工具。"""

from pathlib import Path

from mcp import Client

from merchant_agent.agent.action import make_tool_node
from merchant_agent.agent.graph import build_observation_loop_graph
from merchant_agent.agent.planning import PLANNING_INSTRUCTION
from merchant_agent.agent.runner import run_agent
from merchant_agent.agent.state import AgentState
from merchant_agent.mcp_server import create_server


async def invoke_live_agent(state: AgentState, db_path: Path, trace_path: Path,
                            thread_id: str, *, model,
                            planning_instruction: str = PLANNING_INSTRUCTION) -> AgentState:
    """每次 Trial 新建 MCP 会话和图，使用该 Trial 独立数据库与 Trace。"""
    async with Client(create_server(str(db_path))) as client:
        graph = build_observation_loop_graph(
            model, make_tool_node(client, str(trace_path)), trace_path=str(trace_path),
            planning_instruction=planning_instruction,
        )
        return await run_agent(graph, state, thread_id=thread_id, trace_path=str(trace_path))
