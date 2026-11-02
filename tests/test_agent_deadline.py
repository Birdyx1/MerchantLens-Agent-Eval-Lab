import asyncio
import json
import math

import pytest

from merchant_agent.agent.graph import build_observation_loop_graph
from merchant_agent.agent.model_port import ModelResponse
from merchant_agent.agent.runner import AgentDeadlineExceeded, run_agent
from merchant_agent.agent.state import initial_state


def _initial():
    return initial_state("task-1", "a" * 32, "b" * 16, "问题")


async def unused_tool_node(state):
    raise AssertionError("工具节点不应执行")


def _finish_response():
    return ModelResponse(json.dumps({"plan": [], "action": {"type": "finish", "answer": "完成"}}),
                         "fixed-model", 1, 1)


def test_wall_clock_deadline_marks_unfinished_run():
    class SlowModel:
        async def generate(self, messages):
            await asyncio.sleep(0.1)
            return _finish_response()

    graph = build_observation_loop_graph(SlowModel(), unused_tool_node)
    with pytest.raises(AgentDeadlineExceeded) as error:
        asyncio.run(run_agent(graph, _initial(), timeout_seconds=0.01))
    assert error.value.reason == "deadline"


def test_inner_timeout_is_not_misclassified_as_deadline():
    class FailingModel:
        async def generate(self, messages):
            raise TimeoutError("模型服务超时")

    graph = build_observation_loop_graph(FailingModel(), unused_tool_node)
    with pytest.raises(TimeoutError, match="模型服务超时") as error:
        asyncio.run(run_agent(graph, _initial(), timeout_seconds=1))
    assert not isinstance(error.value, AgentDeadlineExceeded)


def test_external_cancellation_propagates():
    async def run():
        entered = asyncio.Event()

        class SlowModel:
            async def generate(self, messages):
                entered.set()
                await asyncio.sleep(10)
                return _finish_response()

        graph = build_observation_loop_graph(SlowModel(), unused_tool_node)
        task = asyncio.create_task(run_agent(graph, _initial(), timeout_seconds=5))
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(run())


@pytest.mark.parametrize("timeout", [0, -1, True, math.nan, math.inf])
def test_invalid_wall_clock_budget_rejected(timeout):
    class UnusedGraph:
        async def ainvoke(self, state, config):
            raise AssertionError("非法预算不能启动图")

    with pytest.raises(ValueError, match="timeout_seconds"):
        asyncio.run(run_agent(UnusedGraph(), _initial(), timeout_seconds=timeout))
