"""在同一冻结 Regression 清单上运行两版提示词 Harness。"""

import asyncio
import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path

from merchant_agent.agent.deepseek_responses_model import DeepSeekResponsesModel
from merchant_agent.evaluation.base_admission_live import _config
from merchant_agent.evaluation.batch import run_batch
from merchant_agent.evaluation.data_closure_live import _harness_fingerprint
from merchant_agent.evaluation.live_invoke import invoke_live_agent
from merchant_agent.evaluation.pilot_repeated_live import _save
from merchant_agent.evaluation.prompt_harness_experiment import PROMPTS
from merchant_agent.evaluation.report import compare_batches, render_markdown
from merchant_agent.evaluation.sets import EvalCollection


ROOT = Path(__file__).resolve().parents[3]
COLLECTION = EvalCollection.REGRESSION
REPEATS = 2


async def main() -> Path:
    """先冻结清单，再顺序执行两版；结果仅作小样本描述性对比。"""
    key, model_name = _config()
    model = DeepSeekResponsesModel(model_name, key)
    source_fingerprint = _harness_fingerprint()
    task_paths = sorted((ROOT / "eval_sets" / COLLECTION.value / "tasks").glob("*.json"))
    if not task_paths:
        raise ValueError("Regression 集合为空")
    task_manifest = {path.stem: hashlib.sha256(path.read_bytes()).hexdigest() for path in task_paths}
    evaluator_files = ("src/merchant_agent/evaluation/code_evaluator.py",
                       "src/merchant_agent/evaluation/trajectory_evaluator.py",
                       "src/merchant_agent/evaluation/report.py")
    record = {
        "status": "running", "started_at": datetime.now(timezone.utc).isoformat(),
        "collection": COLLECTION.value, "repeats": REPEATS, "model_version": model_name,
        "task_manifest": task_manifest, "source_fingerprint": source_fingerprint,
        "evaluator_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                             for name in evaluator_files},
        "prompt_sha256": {arm: hashlib.sha256(prompt.encode("utf-8")).hexdigest()
                          for arm, prompt in PROMPTS.items()},
        "holdout_used": False, "batches": {}, "comparison": None,
    }
    directory = ROOT / "runs" / "same_task_harness" / uuid.uuid4().hex
    directory.mkdir(parents=True, exist_ok=False, mode=0o700)
    path = directory / "experiment.json"
    _save(path, record)
    completed = {}
    try:
        for arm in ("baseline", "explicit_json_after_tool"):
            if {path.stem: hashlib.sha256(path.read_bytes()).hexdigest() for path in task_paths} != task_manifest:
                raise ValueError("同题对比运行中 Task 快照发生变化")
            prompt = PROMPTS[arm]
            harness_version = f"{source_fingerprint}:prompt-sha256:{record['prompt_sha256'][arm]}"

            def invoke_factory(_task_path: Path, _repeat_index: int):
                async def invoke(state, db_path, trace_path, thread_id):
                    return await invoke_live_agent(state, db_path, trace_path, thread_id,
                                                   model=model, planning_instruction=prompt)
                return invoke

            batch = await run_batch(project_root=ROOT, collection=COLLECTION,
                                    repeats=REPEATS, model_version=model_name,
                                    harness_version=harness_version,
                                    invoke_factory=invoke_factory, timeout_seconds=90)
            completed[arm] = batch
            record["batches"][arm] = {"batch_id": batch["batch_id"], "status": batch["status"],
                                      "aggregate": batch["aggregate"]}
            _save(path, record)
        record["comparison"] = compare_batches(completed["baseline"],
                                                completed["explicit_json_after_tool"])
        (directory / "comparison.md").write_text(render_markdown(record["comparison"]), encoding="utf-8")
        record["status"] = "completed"
    except BaseException as exc:
        record["status"] = "failed"
        record["error_type"] = type(exc).__name__
        raise
    finally:
        record["ended_at"] = datetime.now(timezone.utc).isoformat()
        _save(path, record)
    return path


if __name__ == "__main__":
    print(f"同题双版本记录：{asyncio.run(main())}")
