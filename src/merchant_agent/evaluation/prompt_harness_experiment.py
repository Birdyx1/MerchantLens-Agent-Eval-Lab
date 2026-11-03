"""固定模型与 Task，只改变规划提示词的成对 Harness 试验。"""

import asyncio
import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path

from merchant_agent.agent.deepseek_responses_model import DeepSeekResponsesModel
from merchant_agent.agent.planning import PLANNING_INSTRUCTION
from merchant_agent.evaluation.base_admission_live import _config
from merchant_agent.evaluation.code_evaluator import evaluate_trial
from merchant_agent.evaluation.data_closure_live import _harness_fingerprint
from merchant_agent.evaluation.live_invoke import invoke_live_agent
from merchant_agent.evaluation.metrics import trial_metrics
from merchant_agent.evaluation.pilot_repeated_live import _save
from merchant_agent.evaluation.task import load_eval_task
from merchant_agent.evaluation.trajectory_evaluator import evaluate_trial_trajectory
from merchant_agent.evaluation.trial import run_trial
from merchant_agent.tracing.reader import read_spans


ROOT = Path(__file__).resolve().parents[3]
TASK = ROOT / "eval_sets/regression/tasks/pilot_store_net_g_001.json"
PROMPTS = {
    "baseline": PLANNING_INSTRUCTION,
    "explicit_json_after_tool": PLANNING_INSTRUCTION + (
        "每一轮都必须遵守同一个 JSON 契约，包括收到工具观察后的最终回答。"
        "若工具已返回可用结果，也不要直接输出自然语言；"
        "应返回 {\"plan\":[],\"action\":{\"type\":\"finish\",\"answer\":\"包含结果的答案\"}}。"
        "不要添加 JSON 对象之外的任何字符。"
    ),
}
PAIRS = 5


def summarize_pairs(items: list[dict], *, pairs: int) -> dict:
    """按同一轮次配对，报告描述性差值和不一致对，不声称显著性。"""
    grouped = {}
    for item in items:
        key = (item["pair_index"], item["arm"])
        if key in grouped or item["arm"] not in PROMPTS or not 0 <= item["pair_index"] < pairs:
            raise ValueError("成对试验含重复或越界单元")
        grouped[key] = item
    if len(grouped) != 2 * pairs:
        raise ValueError("成对试验缺少单元")
    baseline = [grouped[index, "baseline"]["passed"] for index in range(pairs)]
    candidate = [grouped[index, "explicit_json_after_tool"]["passed"] for index in range(pairs)]
    return {
        "pairs": pairs,
        "baseline_successes": sum(baseline),
        "candidate_successes": sum(candidate),
        "baseline_rate": sum(baseline) / pairs,
        "candidate_rate": sum(candidate) / pairs,
        "delta_rate": (sum(candidate) - sum(baseline)) / pairs,
        "candidate_only_success_pairs": sum(not old and new for old, new in zip(baseline, candidate)),
        "baseline_only_success_pairs": sum(old and not new for old, new in zip(baseline, candidate)),
        "interpretation": "同题小样本描述性对照；未固定模型随机种子，不能证明因果或显著提升",
    }


def _failure_layer(trial: dict, score: dict, trace_path: Path) -> str | None:
    """从失败 Span 归因，避免把网络故障或安全拒绝计作模型契约错误。"""
    if score["passed"]:
        return None
    if trace_path.is_file():
        for span in read_spans(str(trace_path)):
            attrs = span.get("attributes", {})
            if (span.get("name") == "model.plan" and attrs.get("outcome") == "error"
                    and attrs.get("error_type") == "ValueError" and "model_output" in attrs):
                return "model_contract"
    return "answer_or_process" if trial["status"] == "completed" else "execution_error"


async def main() -> Path:
    """交替执行 AB/BA，逐 Trial 保存证据；Holdout 不参与。"""
    key, model_name = _config()
    task = load_eval_task(TASK, project_root=ROOT)
    if task.label_status != "adjudicated":
        raise ValueError("试验 Task 必须已仲裁")
    source_fingerprint = _harness_fingerprint()
    model = DeepSeekResponsesModel(model_name, key)
    directory = ROOT / "runs" / "prompt_harness" / uuid.uuid4().hex
    directory.mkdir(parents=True, exist_ok=False, mode=0o700)
    path = directory / "experiment.json"
    plan = {
        "status": "running", "started_at": datetime.now(timezone.utc).isoformat(),
        "task_id": task.task_id, "task_sha256": hashlib.sha256(TASK.read_bytes()).hexdigest(),
        "fixture_sha256": hashlib.sha256(task.fixture_path.read_bytes()).hexdigest(),
        "rubric_sha256": task.rubric_sha256, "model_version": model_name,
        "source_fingerprint": source_fingerprint,
        "evaluator_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                             for name in ("src/merchant_agent/evaluation/code_evaluator.py",
                                          "src/merchant_agent/evaluation/trajectory_evaluator.py")},
        "prompt_sha256": {name: hashlib.sha256(prompt.encode("utf-8")).hexdigest()
                          for name, prompt in PROMPTS.items()},
        "pairs": PAIRS, "holdout_used": False, "items": [], "summary": None,
    }
    _save(path, plan)
    try:
        for pair_index in range(PAIRS):
            order = ("baseline", "explicit_json_after_tool") if pair_index % 2 == 0 else (
                "explicit_json_after_tool", "baseline")
            for arm in order:
                prompt = PROMPTS[arm]
                harness_version = f"{source_fingerprint}:prompt-sha256:{plan['prompt_sha256'][arm]}"

                async def invoke(state, db_path, trace_path, thread_id):
                    return await invoke_live_agent(state, db_path, trace_path, thread_id,
                                                   model=model, planning_instruction=prompt)

                trial = await run_trial(TASK, project_root=ROOT, invoke=invoke,
                                        model_version=model_name, harness_version=harness_version,
                                        timeout_seconds=90)
                score = evaluate_trial(trial, TASK, project_root=ROOT)
                trajectory = evaluate_trial_trajectory(trial, TASK, project_root=ROOT)
                metrics = trial_metrics(trial, score, project_root=ROOT)
                plan["items"].append({
                    "pair_index": pair_index, "arm": arm, "trial_id": trial["trial_id"],
                    "trial_status": trial["status"], "trace_sha256": trial["trace_sha256"],
                    "passed": score["passed"] and trajectory["trajectory_passed"],
                    "result_passed": trajectory["result_passed"],
                    "trajectory_passed": trajectory["trajectory_passed"],
                    "failure_layer": _failure_layer(trial, score, ROOT / trial["trace_path"]),
                    "total_tokens": metrics["total_tokens"],
                    "safety_status": metrics["safety_status"],
                })
                _save(path, plan)
        plan["summary"] = summarize_pairs(plan["items"], pairs=PAIRS)
        plan["status"] = "completed"
    except BaseException as exc:
        plan["status"] = "failed"
        plan["error_type"] = type(exc).__name__
        raise
    finally:
        plan["ended_at"] = datetime.now(timezone.utc).isoformat()
        _save(path, plan)
    return path


if __name__ == "__main__":
    print(f"Harness 对照记录：{asyncio.run(main())}")
