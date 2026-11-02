import asyncio
import hashlib
import json
from pathlib import Path

import pytest

from merchant_agent.agent.model_port import ModelResponse
from merchant_agent.evaluation.agent_judge import judge_with_evidence


ROOT = Path(__file__).resolve().parents[1]


class TwoStepJudge:
    def __init__(self, *outputs):
        self.outputs = list(outputs)
        self.calls = []

    async def generate(self, messages):
        self.calls.append(messages)
        return ModelResponse(json.dumps(self.outputs[len(self.calls) - 1]), "judge-agent-v1", 10, 4)


def _case(tmp_path):
    for relative in ("schemas/eval_task.schema.json", "fixtures/business_data/orders.csv"):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / relative).read_bytes())
    task = tmp_path / "eval_sets/golden/tasks/store_net_a_001.json"
    task.parent.mkdir(parents=True)
    task.write_bytes((ROOT / "fixtures/eval_task_examples/store_net_a.json").read_bytes())
    trace = tmp_path / "runs/trials/trial_1/trace.jsonl"
    trace.parent.mkdir(parents=True)
    trace.write_text(json.dumps({"trace_id": "a" * 32, "span_id": "b" * 16,
                                 "name": "agent.request", "attributes": {"task_id": "store_net_a_001"}}) + "\n")
    trial = {"trial_id": "trial_1", "task_id": "store_net_a_001", "final_answer": "12000 分",
             "trace_path": "runs/trials/trial_1/trace.jsonl",
             "trace_sha256": hashlib.sha256(trace.read_bytes()).hexdigest()}
    code = {"trial_id": "trial_1", "task_id": "store_net_a_001", "trace_valid": True,
            "passed": True}
    return task, trial, code


def test_agent_judge_actively_verifies_frozen_data(tmp_path):
    task, trial, code = _case(tmp_path)
    judge = TwoStepJudge({"action": "verify_store_net", "store_id": "A"},
                         {"action": "finish", "verdict": "pass", "reason": "核验金额一致"})
    result = asyncio.run(judge_with_evidence(trial, code, task, project_root=tmp_path, model=judge))
    assert result["verification"] == {"store_id": "A", "result_fen": 12000}
    assert result["requires_human_review"] is False
    assert len(judge.calls) == 2
    assert json.loads(judge.calls[1][-1]["content"])["tool_result"]["result_fen"] == 12000


def test_wrong_tool_target_is_rejected(tmp_path):
    task, trial, code = _case(tmp_path)
    judge = TwoStepJudge({"action": "verify_store_net", "store_id": "B"},
                         {"action": "finish", "verdict": "pass", "reason": "无效"})
    with pytest.raises(ValueError, match="目标门店"):
        asyncio.run(judge_with_evidence(trial, code, task, project_root=tmp_path, model=judge))
    assert len(judge.calls) == 1


def test_conflict_with_code_requires_human_review(tmp_path):
    task, trial, code = _case(tmp_path)
    judge = TwoStepJudge({"action": "verify_store_net", "store_id": "A"},
                         {"action": "finish", "verdict": "fail", "reason": "证据链有疑问"})
    result = asyncio.run(judge_with_evidence(trial, code, task, project_root=tmp_path, model=judge))
    assert result["requires_human_review"] is True


def test_untrusted_trace_is_rejected_before_model_call(tmp_path):
    task, trial, code = _case(tmp_path)
    trial["trace_sha256"] = "0" * 64
    judge = TwoStepJudge({"action": "verify_store_net", "store_id": "A"},
                         {"action": "finish", "verdict": "pass", "reason": "好"})
    with pytest.raises(ValueError, match="哈希"):
        asyncio.run(judge_with_evidence(trial, code, task, project_root=tmp_path, model=judge))
    assert judge.calls == []


def test_agent_can_inspect_span_then_verify_then_finish(tmp_path):
    task, trial, code = _case(tmp_path)
    judge = TwoStepJudge(
        {"action": "inspect_span", "span_id": "b" * 16},
        {"action": "verify_store_net", "store_id": "A"},
        {"action": "finish", "verdict": "pass", "reason": "轨迹与冻结数据一致"},
    )
    result = asyncio.run(judge_with_evidence(trial, code, task, project_root=tmp_path, model=judge))
    assert [step["action"] for step in result["judge_steps"]] == [
        "inspect_span", "verify_store_net", "finish"
    ]
    assert result["input_tokens"] == 30


def test_agent_cannot_finish_without_verification(tmp_path):
    task, trial, code = _case(tmp_path)
    judge = TwoStepJudge({"action": "finish", "verdict": "pass", "reason": "猜测"})
    with pytest.raises(ValueError, match="先核验"):
        asyncio.run(judge_with_evidence(trial, code, task, project_root=tmp_path, model=judge))
