"""重放四格真实 Trial 的首个规划输出，按冻结 Task 期望诊断组件。"""

import hashlib
import json
import uuid
from pathlib import Path

from merchant_agent.agent.state import initial_state
from merchant_agent.evaluation.pilot_repeated_live import _save
from merchant_agent.evaluation.planning_component import PlanningCase, evaluate_planning_case, summarize_planning_cases
from merchant_agent.evaluation.task import load_eval_task


ROOT = Path(__file__).resolve().parents[3]
EXPERIMENT = ROOT / "runs/model_harness_matrix/489a0692a3e34f5396ba3a4b43466f25/experiment.json"


def main() -> Path:
    """只读取已有 Trace；首步期望来自 Task 的固定工具与参数。"""
    raw = EXPERIMENT.read_bytes()
    experiment = json.loads(raw)
    if experiment.get("status") != "completed" or len(experiment.get("completed", [])) != 32:
        raise ValueError("四格实验未完整完成")
    manifest = {item["task_id"]: item for item in experiment["manifest"]}
    results = []
    for item in experiment["completed"]:
        task_entry = manifest[item["task_id"]]
        task_path = ROOT / task_entry["path"]
        if hashlib.sha256(task_path.read_bytes()).hexdigest() != task_entry["sha256"]:
            raise ValueError("Task 摘要不一致")
        task = load_eval_task(task_path, project_root=ROOT)
        trial_path = ROOT / "runs/trials" / item["trial_id"] / "trial.json"
        trial = json.loads(trial_path.read_bytes())
        trace_path = ROOT / trial["trace_path"]
        trace_bytes = trace_path.read_bytes()
        if hashlib.sha256(trace_bytes).hexdigest() != trial["trace_sha256"]:
            raise ValueError("Trace 摘要不一致")
        spans = [json.loads(line) for line in trace_bytes.splitlines()]
        plans = sorted((span for span in spans if span["name"] == "model.plan"),
                       key=lambda span: span["start_time"])
        if not plans or "model_output" not in plans[0]["attributes"]:
            raise ValueError("缺少首个模型规划输出")
        span = plans[0]
        attrs = span["attributes"]
        state = initial_state(task.task_id, trial["trace_id"], span["parent_span_id"], task.user_request)
        state["step_count"] = 1
        state["input_tokens"] = attrs["input_tokens"]
        state["output_tokens"] = attrs["output_tokens"]
        case = PlanningCase(item["trial_id"], attrs["model_output"], "tool",
                            task.required_tool_name, dict(task.required_tool_arguments))
        result = evaluate_planning_case(case, state)
        results.append({**result, "task_id": task.task_id, "model": item["model_key"],
                        "harness": item["arm"], "trace_sha256": trial["trace_sha256"]})
    directory = ROOT / "runs/planning_replay" / uuid.uuid4().hex
    directory.mkdir(parents=True, exist_ok=False, mode=0o700)
    target = directory / "results.json"
    _save(target, {"experiment_sha256": hashlib.sha256(raw).hexdigest(),
                   "evaluator_sha256": hashlib.sha256((ROOT / "src/merchant_agent/evaluation/planning_component.py").read_bytes()).hexdigest(),
                   "scope": "每条 Trial 首次规划；期望来自冻结 Task", "summary": summarize_planning_cases(results),
                   "results": results})
    return target


if __name__ == "__main__":
    print(f"规划组件重放记录：{main()}")
