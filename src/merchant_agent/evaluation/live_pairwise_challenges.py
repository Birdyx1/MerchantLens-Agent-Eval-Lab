"""用真实模型对同一虚构任务的不同清晰度回答做双顺序成对比较。"""

import asyncio
import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from merchant_agent.agent.siliconflow_chat_model import SiliconFlowChatModel
from merchant_agent.evaluation.live_siliconflow_panel_challenges import _config
from merchant_agent.evaluation.pairwise_judge import compare_answers
from merchant_agent.evaluation.pilot_repeated_live import _save


ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "fixtures/judge_clarity_challenges_v1.json"
REFERENCE = ROOT / "runs/judge_challenges/9bb83c88363545acaaf41a646543785a/calibration.json"
PAIRS = (("no_conclusion", "missing_unit"),
         ("missing_unit", "clear_fen"),
         ("contradictory_amounts", "clear_conversion"))


async def main() -> Path:
    """每对交换位置各调用一次；不把设计分数或人工分数发给裁判。"""
    fixture_bytes = FIXTURE.read_bytes()
    fixture = json.loads(fixture_bytes)
    cases = {case["case_id"]: case for case in fixture["cases"]}
    reference_bytes = REFERENCE.read_bytes()
    reference = json.loads(reference_bytes)
    if (len(cases) != len(fixture["cases"]) or len(cases) != 6
            or reference.get("fixture_sha256") != hashlib.sha256(fixture_bytes).hexdigest()
            or reference.get("sample_size") != 6
            or any(row["reference_score"] is None for row in reference["rows"])
            or any(left not in cases or right not in cases or left == right for left, right in PAIRS)):
        raise ValueError("成对挑战与人工参考分不一致")
    key, models = _config()
    model = SiliconFlowChatModel(models[0], key, json_mode=True)
    directory = ROOT / "runs/pairwise_challenges" / uuid.uuid4().hex
    directory.mkdir(parents=True, exist_ok=False, mode=0o700)
    target = directory / "results.json"
    task_hash = hashlib.sha256((ROOT / "fixtures/eval_task_examples/store_net_a.json").read_bytes()).hexdigest()
    record = {"status": "running", "started_at": datetime.now(timezone.utc).isoformat(),
              "fixture_sha256": hashlib.sha256(fixture_bytes).hexdigest(),
              "human_reference_sha256": hashlib.sha256(reference_bytes).hexdigest(),
              "pairwise_source_sha256": hashlib.sha256((ROOT / "src/merchant_agent/evaluation/pairwise_judge.py").read_bytes()).hexdigest(),
              "task_id": "store_net_a_001", "task_sha256": task_hash,
              "judge_model_config": models[0], "holdout_used": False,
              "judge_parameters": {"response_format": {"type": "json_object"}},
              "provenance": "人工构造的同题替代回答，非真实 Agent Trial", "results": []}
    _save(target, record)
    try:
        for left, right in PAIRS:
            first = {"trial_id": f"synthetic-{left}", "task_id": record["task_id"],
                     "task_sha256": task_hash, "final_answer": cases[left]["answer"]}
            second = {"trial_id": f"synthetic-{right}", "task_id": record["task_id"],
                      "task_sha256": task_hash, "final_answer": cases[right]["answer"]}
            result = await compare_answers(first, second, project_root=ROOT, model=model)
            record["results"].append({"first_case_id": left, "second_case_id": right,
                                      "comparison": result})
            _save(target, record)
        record["status"] = "completed"
    except BaseException as exc:
        record["status"] = "failed"
        record["error_type"] = type(exc).__name__
        record["error_detail"] = str(exc) if isinstance(exc, ValueError) else None
        raise
    finally:
        record["ended_at"] = datetime.now(timezone.utc).isoformat()
        _save(target, record)
    return target


if __name__ == "__main__":
    print(f"成对挑战记录：{asyncio.run(main())}")
