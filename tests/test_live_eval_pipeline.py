import asyncio
import json
from pathlib import Path

from merchant_agent.agent.model_port import ModelResponse
from merchant_agent.evaluation.code_evaluator import evaluate_trial
from merchant_agent.evaluation.live_invoke import invoke_live_agent
from merchant_agent.evaluation.metrics import trial_metrics
from merchant_agent.evaluation.trial import run_trial
from merchant_agent.evaluation.trajectory_evaluator import evaluate_trial_trajectory


ROOT = Path(__file__).resolve().parents[1]


class EvidenceModel:
    """测试模型必须见到本次 MCP SQL 观察才结束。"""

    async def generate(self, messages):
        observations = [json.loads(item["content"]) for item in messages if item["role"] == "tool"]
        if observations:
            action = {"type": "finish", "answer": f"门店 A 净收入为 {observations[-1]['result_fen']} 分"}
        else:
            action = {"type": "tool", "name": "get_store_net", "arguments": {"store_id": "A"}}
        return ModelResponse(json.dumps({"plan": ["核对订单"], "action": action}),
                             "fixture-model", 8, 4)


def test_trial_to_mcp_graph_trace_score_and_metrics(tmp_path):
    for relative in (
        "schemas/eval_task.schema.json", "schemas/rubric.schema.json", "schemas/span.schema.json",
        "rubrics/store_net_v1.json", "fixtures/business_data/orders.csv",
    ):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / relative).read_bytes())
    task = tmp_path / "eval_sets/golden/tasks/store_net_a_001.json"
    task.parent.mkdir(parents=True)
    task.write_bytes((ROOT / "fixtures/eval_task_examples/store_net_a.json").read_bytes())

    async def invoke(state, db_path, trace_path, thread_id):
        return await invoke_live_agent(state, db_path, trace_path, thread_id, model=EvidenceModel())

    trial = asyncio.run(run_trial(task, project_root=tmp_path, invoke=invoke,
                                  model_version="fixture-model", harness_version="harness-test"))
    score = evaluate_trial(trial, task, project_root=tmp_path)
    row = trial_metrics(trial, score, project_root=tmp_path)
    assert trial["status"] == "completed"
    assert trial["trace_status"] == "present"
    assert score["passed"] is True
    assert row["overall_success"] is True
    assert row["tool_calls"] == 1
    assert row["total_tokens"] == 24
    trajectory = evaluate_trial_trajectory(trial, task, project_root=tmp_path)
    assert trajectory["passed"] is True
    assert all(trajectory["checks"].values())

    # 保留同样的答案和工具结果，仅移动最终决策到取证前；旧结果裁判仍能通过。
    trace_path = tmp_path / trial["trace_path"]
    spans = [json.loads(line) for line in trace_path.read_text().splitlines()]
    spans[1], spans[2] = spans[2], spans[1]
    trace_path.write_text("".join(json.dumps(span) + "\n" for span in spans))
    import hashlib
    trial["trace_sha256"] = hashlib.sha256(trace_path.read_bytes()).hexdigest()
    assert evaluate_trial(trial, task, project_root=tmp_path)["passed"] is True
    reordered = evaluate_trial_trajectory(trial, task, project_root=tmp_path)
    assert reordered["result_passed"] is True
    assert reordered["trajectory_passed"] is False
    assert reordered["failure_mode"] == "ungrounded_or_wrong_order"
