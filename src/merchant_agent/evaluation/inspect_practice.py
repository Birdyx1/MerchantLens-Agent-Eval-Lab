"""Inspect AI 小规模框架接入练习；使用规则测试模型，不代表基座能力。"""

import json
import uuid
from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.dataset import Sample
from inspect_ai.model import ModelOutput
from inspect_ai.scorer import CORRECT, INCORRECT, Score, Target, accuracy, scorer
from inspect_ai.solver import Generate, Solver, TaskState, solver

from merchant_agent.agent.model_port import ModelResponse
from merchant_agent.agent.state import initial_state
from merchant_agent.evaluation.live_invoke import invoke_live_agent
from merchant_agent.evaluation.reference import store_net_from_fixture
from merchant_agent.evaluation.code_evaluator import _answer_amount
from merchant_agent.tools.sql.init_orders_db import create_orders_db
from merchant_agent.tracing.reader import read_spans
from merchant_agent.tracing.validator import validate_trace


PROJECT_ROOT = Path(__file__).resolve().parents[3]
FIXTURE = PROJECT_ROOT / "fixtures/business_data/orders.csv"


class RuleFixtureModel:
    """仅用于验证框架接线；从请求读取门店并依据工具观察结束。"""

    async def generate(self, messages):
        request = next(item["content"] for item in messages if item["role"] == "user")
        store_id = "A" if "A" in request else "B"
        observations = [json.loads(item["content"]) for item in messages if item["role"] == "tool"]
        if observations:
            action = {"type": "finish", "answer": f"门店 {store_id} 净收入为 {observations[-1]['result_fen']} 分"}
        else:
            action = {"type": "tool", "name": "get_store_net", "arguments": {"store_id": store_id}}
        return ModelResponse(json.dumps({"plan": ["查询订单"], "action": action}),
                             "rule-fixture-model", 8, 4)


@solver
def merchant_agent_solver() -> Solver:
    """把已有 LangGraph/MCP Agent 作为 Inspect Solver 调用。"""
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        run_id = uuid.uuid4().hex
        directory = PROJECT_ROOT / "runs/inspect_practice" / run_id
        directory.mkdir(parents=True, exist_ok=False, mode=0o700)
        db_path = directory / "orders.sqlite"
        trace_path = directory / "trace.jsonl"
        create_orders_db(str(FIXTURE), str(db_path))
        agent_state = initial_state(str(state.sample_id), uuid.uuid4().hex,
                                    uuid.uuid4().hex[:16], str(state.input_text))
        result = await invoke_live_agent(agent_state, db_path, trace_path,
                                         f"inspect-{run_id}", model=RuleFixtureModel())
        state.output = ModelOutput.from_content("rule-fixture-model", result.get("final_answer") or "")
        state.metadata["trace_path"] = str(trace_path)
        state.metadata["trace_id"] = agent_state["trace_id"]
        state.metadata["termination_reason"] = result.get("termination_reason")
        return state
    return solve


@scorer(metrics=[accuracy()])
def merchant_trace_scorer():
    """Inspect Score 同时要求金额正确和目标门店成功工具调用。"""
    async def score(state: TaskState, target: Target) -> Score:
        answer = state.output.completion
        store_id = state.metadata["store_id"]
        spans = read_spans(state.metadata["trace_path"])
        tool_ok = any(span["name"] == "tool.get_store_net"
                      and span["attributes"].get("store_id") == store_id
                      and span["attributes"].get("outcome") == "success"
                      and str(span["attributes"].get("result_fen")) == target.text
                      for span in spans)
        trace_ok = not validate_trace(spans) and all(
            span["trace_id"] == state.metadata["trace_id"] for span in spans
        )
        passed = (_answer_amount(answer) == int(target.text) and tool_ok and trace_ok
                  and state.metadata["termination_reason"] == "completed")
        return Score(value=CORRECT if passed else INCORRECT, answer=answer,
                     explanation="金额、目标门店工具返回和 Trace 均核验" if passed else "结果或轨迹不匹配")
    return score


@task
def merchant_store_net_practice() -> Task:
    """两道自建门店题；不是公开 Benchmark，也不进入正式黄金集。"""
    samples = [Sample(id=f"inspect_store_{store_id.lower()}",
                      input=f"请查询门店 {store_id} 的净收入，单位分。",
                      target=str(store_net_from_fixture(FIXTURE, store_id)),
                      metadata={"store_id": store_id}) for store_id in ("A", "B")]
    return Task(dataset=samples, solver=merchant_agent_solver(), scorer=merchant_trace_scorer())
