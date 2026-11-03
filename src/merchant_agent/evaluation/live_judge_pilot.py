"""对冻结批次的真实 Trial 运行固定 Rubric 裁判，并保存可追溯结果。"""

import asyncio
import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from merchant_agent.agent.deepseek_responses_model import DeepSeekResponsesModel
from merchant_agent.evaluation.base_admission_live import _config
from merchant_agent.evaluation.llm_judge import RUBRIC_PATH, judge_answer_clarity
from merchant_agent.evaluation.pilot_repeated_live import _save


ROOT = Path(__file__).resolve().parents[3]
BATCH_ID = "5c34fc4ea2cc4a0db191596f6dd04ecd"


async def main() -> Path:
    """每题选择首个 Trial；裁判只评清晰度，不修改原始 Code 分数。"""
    batch_path = ROOT / "runs" / "batches" / BATCH_ID / "batch.json"
    batch_bytes = batch_path.read_bytes()
    batch = json.loads(batch_bytes)
    if batch["status"] != "completed" or batch["collection"] != "regression":
        raise ValueError("只接受已完成的 Regression 批次")
    selected = {}
    for item in batch["items"]:
        if item["repeat_index"] == 0 and item["score"] is not None:
            selected[item["task_id"]] = item
    if len(selected) != len(batch["manifest"]):
        raise ValueError("首轮 Trial 与冻结任务清单不一致")

    key, model_name = _config()
    model = DeepSeekResponsesModel(model_name, key)
    directory = ROOT / "runs" / "judge_pilot" / uuid.uuid4().hex
    directory.mkdir(parents=True, exist_ok=False, mode=0o700)
    output = directory / "results.json"
    record = {
        "status": "running", "created_at": datetime.now(timezone.utc).isoformat(),
        "batch_id": BATCH_ID, "batch_sha256": hashlib.sha256(batch_bytes).hexdigest(),
        "rubric_sha256": hashlib.sha256((ROOT / RUBRIC_PATH).read_bytes()).hexdigest(),
        "judge_source_sha256": hashlib.sha256((ROOT / "src/merchant_agent/evaluation/llm_judge.py").read_bytes()).hexdigest(),
        "judge_model_config": model_name, "selection": "每题 repeat_index=0", "results": [],
    }
    _save(output, record)
    try:
        for task_id, item in sorted(selected.items()):
            trial_path = ROOT / "runs" / "trials" / item["trial_id"] / "trial.json"
            trial_bytes = trial_path.read_bytes()
            trial = json.loads(trial_bytes)
            if trial["trial_id"] != item["trial_id"] or trial["task_id"] != task_id:
                raise ValueError("批次与 Trial 身份不一致")
            result = await judge_answer_clarity(trial, item["score"], project_root=ROOT, model=model)
            record["results"].append({"task_id": task_id, "trial_id": trial["trial_id"],
                                      "trial_sha256": hashlib.sha256(trial_bytes).hexdigest(),
                                      "code_passed": item["score"]["passed"], "judge": result})
            _save(output, record)
        record["status"] = "completed"
    except BaseException as exc:
        record["status"] = "failed"
        record["error_type"] = type(exc).__name__
        raise
    finally:
        record["ended_at"] = datetime.now(timezone.utc).isoformat()
        _save(output, record)
    return output


if __name__ == "__main__":
    print(f"真实裁判记录：{asyncio.run(main())}")
