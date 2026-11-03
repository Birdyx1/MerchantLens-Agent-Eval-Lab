"""在固定虚构挑战上运行三次真实裁判调用，记录逐票与多数结论。"""

import asyncio
import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from merchant_agent.agent.deepseek_responses_model import DeepSeekResponsesModel
from merchant_agent.evaluation.base_admission_live import _config
from merchant_agent.evaluation.judge_panel import JudgeSpec, run_judge_panel
from merchant_agent.evaluation.llm_judge import RUBRIC_PATH
from merchant_agent.evaluation.pilot_repeated_live import _save


ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "fixtures/judge_clarity_challenges_v1.json"
REFERENCE = ROOT / "runs/judge_challenges/9bb83c88363545acaaf41a646543785a/calibration.json"


async def main() -> Path:
    """三次调用独立发起，但同模型家族的错误可能相关。"""
    fixture_bytes = FIXTURE.read_bytes()
    fixture = json.loads(fixture_bytes)
    if (fixture.get("fixture_id") != "judge_clarity_challenges_v1"
            or len(fixture.get("cases", [])) != 6):
        raise ValueError("挑战集契约无效")
    reference_bytes = REFERENCE.read_bytes()
    reference = json.loads(reference_bytes)
    if (reference.get("sample_size") != 6
            or reference.get("fixture_sha256") != hashlib.sha256(fixture_bytes).hexdigest()
            or any(row["reference_score"] is None for row in reference["rows"])):
        raise ValueError("真人双标参考分未完成或挑战集已变更")
    key, model_name = _config()
    judges = [JudgeSpec(f"{model_name}_call_{index}", DeepSeekResponsesModel(model_name, key))
              for index in (1, 2, 3)]
    directory = ROOT / "runs/judge_panels" / uuid.uuid4().hex
    directory.mkdir(parents=True, exist_ok=False, mode=0o700)
    target = directory / "results.json"
    record = {"status": "running", "started_at": datetime.now(timezone.utc).isoformat(),
              "fixture_id": fixture["fixture_id"],
              "fixture_sha256": hashlib.sha256(fixture_bytes).hexdigest(),
              "rubric_sha256": hashlib.sha256((ROOT / RUBRIC_PATH).read_bytes()).hexdigest(),
              "panel_source_sha256": hashlib.sha256((ROOT / "src/merchant_agent/evaluation/judge_panel.py").read_bytes()).hexdigest(),
              "judge_source_sha256": hashlib.sha256((ROOT / "src/merchant_agent/evaluation/llm_judge.py").read_bytes()).hexdigest(),
              "judge_model_config": model_name,
              "judge_design": "three_distinct_instances_same_model_family",
              "human_reference_path": str(REFERENCE.relative_to(ROOT)),
              "human_reference_sha256": hashlib.sha256(reference_bytes).hexdigest(),
              "holdout_used": False, "results": []}
    _save(target, record)
    try:
        for case in fixture["cases"]:
            trial_id = f"synthetic-{case['case_id']}"
            task_id = "synthetic_clarity_probe"
            trial = {"trial_id": trial_id, "task_id": task_id, "final_answer": case["answer"]}
            code_score = {"trial_id": trial_id, "task_id": task_id, "passed": False}
            panel = await run_judge_panel(trial, code_score, project_root=ROOT, judges=judges)
            record["results"].append({"case_id": case["case_id"], "panel": panel})
            _save(target, record)
        record["status"] = "completed"
    except BaseException as exc:
        record["status"] = "failed"
        record["error_type"] = type(exc).__name__
        raise
    finally:
        record["ended_at"] = datetime.now(timezone.utc).isoformat()
        _save(target, record)
    return target


if __name__ == "__main__":
    print(f"真实三次裁判记录：{asyncio.run(main())}")
