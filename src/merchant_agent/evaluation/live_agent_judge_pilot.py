"""对一条冻结 Regression Trial 运行真实 Agent 裁判并保存逐步核验证据。"""

import asyncio
import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from merchant_agent.agent.siliconflow_chat_model import SiliconFlowChatModel
from merchant_agent.evaluation.agent_judge import judge_with_evidence
from merchant_agent.evaluation.live_siliconflow_panel_challenges import _config
from merchant_agent.evaluation.pilot_repeated_live import _save


ROOT = Path(__file__).resolve().parents[3]
BATCH_ID = "5c34fc4ea2cc4a0db191596f6dd04ecd"
TASK_ID = "pilot_store_net_e_001"
REPEAT_INDEX = 0


async def main() -> Path:
    """冻结本次 Trial/Task/Code 评分；裁判只读回放，不改原始证据。"""
    batch_path = ROOT / "runs/batches" / BATCH_ID / "batch.json"
    batch_bytes = batch_path.read_bytes()
    batch = json.loads(batch_bytes)
    if batch.get("status") != "completed" or batch.get("collection") != "regression":
        raise ValueError("试点必须使用已完成的 Regression 批次")
    items = [item for item in batch["items"] if item["task_id"] == TASK_ID
             and item["repeat_index"] == REPEAT_INDEX]
    manifest = [entry for entry in batch["manifest"] if entry["task_id"] == TASK_ID]
    if len(items) != 1 or len(manifest) != 1 or items[0].get("score") is None:
        raise ValueError("冻结 Trial 或 Code 评分缺失")
    item = items[0]
    task_path = ROOT / manifest[0]["path"]
    task_bytes = task_path.read_bytes()
    if hashlib.sha256(task_bytes).hexdigest() != manifest[0]["sha256"]:
        raise ValueError("Task 摘要与批次清单不一致")
    trial_path = ROOT / "runs/trials" / item["trial_id"] / "trial.json"
    trial_bytes = trial_path.read_bytes()
    trial = json.loads(trial_bytes)
    if trial.get("trial_id") != item["trial_id"] or trial.get("task_id") != TASK_ID:
        raise ValueError("Trial 身份与批次不一致")
    key, models = _config()
    model = SiliconFlowChatModel(models[0], key)
    directory = ROOT / "runs/agent_judge_pilot" / uuid.uuid4().hex
    directory.mkdir(parents=True, exist_ok=False, mode=0o700)
    target = directory / "result.json"
    record = {"status": "running", "started_at": datetime.now(timezone.utc).isoformat(),
              "batch_id": BATCH_ID, "batch_sha256": hashlib.sha256(batch_bytes).hexdigest(),
              "task_id": TASK_ID, "task_sha256": hashlib.sha256(task_bytes).hexdigest(),
              "trial_id": trial["trial_id"], "trial_sha256": hashlib.sha256(trial_bytes).hexdigest(),
              "trace_sha256": trial["trace_sha256"],
              "code_score": item["score"], "judge_model_config": models[0],
              "judge_source_sha256": hashlib.sha256((ROOT / "src/merchant_agent/evaluation/agent_judge.py").read_bytes()).hexdigest(),
              "adapter_source_sha256": hashlib.sha256((ROOT / "src/merchant_agent/agent/siliconflow_chat_model.py").read_bytes()).hexdigest(),
              "holdout_used": False, "judge_result": None}
    _save(target, record)
    try:
        record["judge_result"] = await judge_with_evidence(
            trial, item["score"], task_path, project_root=ROOT, model=model)
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
    print(f"真实 Agent 裁判记录：{asyncio.run(main())}")
