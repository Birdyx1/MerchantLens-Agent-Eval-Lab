"""用硅基流动三个不同模型家族运行已双标的虚构挑战。"""

import asyncio
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from merchant_agent.agent.siliconflow_chat_model import SiliconFlowChatModel
from merchant_agent.evaluation.judge_panel import JudgeSpec, run_judge_panel
from merchant_agent.evaluation.llm_judge import RUBRIC_PATH
from merchant_agent.evaluation.pilot_repeated_live import _save


ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "fixtures/judge_clarity_challenges_v1.json"
REFERENCE = ROOT / "runs/judge_challenges/9bb83c88363545acaaf41a646543785a/calibration.json"
MODEL_KEYS = tuple(f"SILICONFLOW_JUDGE_MODEL_{index}" for index in (1, 2, 3))


def _config() -> tuple[str, tuple[str, str, str]]:
    """只读取硅基流动相关键，不打印或保存 API Key。"""
    values = {}
    path = ROOT / ".env"
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition("=")
            if separator and key.strip() in {"SILICONFLOW_API_KEY", *MODEL_KEYS}:
                values[key.strip()] = value.strip().strip("\"'")
    key = os.environ.get("SILICONFLOW_API_KEY") or values.get("SILICONFLOW_API_KEY")
    models = tuple(os.environ.get(name) or values.get(name) for name in MODEL_KEYS)
    if not key or any(not name for name in models) or len(set(models)) != 3:
        raise ValueError("需要 API Key 和三个不同的裁判模型名")
    return key, models


async def main() -> Path:
    """先在首题校验三模型契约；失败即停并保留已运行证据。"""
    fixture_bytes = FIXTURE.read_bytes()
    fixture = json.loads(fixture_bytes)
    reference_bytes = REFERENCE.read_bytes()
    reference = json.loads(reference_bytes)
    if (fixture.get("fixture_id") != "judge_clarity_challenges_v1"
            or len(fixture.get("cases", [])) != 6
            or reference.get("fixture_sha256") != hashlib.sha256(fixture_bytes).hexdigest()
            or reference.get("sample_size") != 6):
        raise ValueError("挑战集或真人双标参考分无效")
    key, models = _config()
    judges = [JudgeSpec(f"siliconflow_model_{index}", SiliconFlowChatModel(
        name, key, enable_thinking=False if name.startswith("Qwen/") else None))
              for index, name in enumerate(models, 1)]
    directory = ROOT / "runs/siliconflow_panels" / uuid.uuid4().hex
    directory.mkdir(parents=True, exist_ok=False, mode=0o700)
    target = directory / "results.json"
    record = {"status": "running", "started_at": datetime.now(timezone.utc).isoformat(),
              "fixture_id": fixture["fixture_id"],
              "fixture_sha256": hashlib.sha256(fixture_bytes).hexdigest(),
              "rubric_sha256": hashlib.sha256((ROOT / RUBRIC_PATH).read_bytes()).hexdigest(),
              "human_reference_sha256": hashlib.sha256(reference_bytes).hexdigest(),
              "judge_source_sha256": hashlib.sha256((ROOT / "src/merchant_agent/evaluation/llm_judge.py").read_bytes()).hexdigest(),
              "panel_source_sha256": hashlib.sha256((ROOT / "src/merchant_agent/evaluation/judge_panel.py").read_bytes()).hexdigest(),
              "adapter_source_sha256": hashlib.sha256((ROOT / "src/merchant_agent/agent/siliconflow_chat_model.py").read_bytes()).hexdigest(),
              "provider": "siliconflow", "models": list(models),
              "judge_design": "three_model_families_one_provider",
              "model_parameters": {name: {"enable_thinking": False} for name in models
                                   if name.startswith("Qwen/")},
              "holdout_used": False, "results": []}
    _save(target, record)
    try:
        for index, case in enumerate(fixture["cases"]):
            trial_id = f"synthetic-{case['case_id']}"
            task_id = "synthetic_clarity_probe"
            trial = {"trial_id": trial_id, "task_id": task_id, "final_answer": case["answer"]}
            code_score = {"trial_id": trial_id, "task_id": task_id, "passed": False}
            panel = await run_judge_panel(trial, code_score, project_root=ROOT, judges=judges)
            record["results"].append({"case_id": case["case_id"], "panel": panel})
            _save(target, record)
            if index == 0 and panel["status"] == "incomplete":
                raise RuntimeError("首题连通性或评分契约未通过，已停止后续调用")
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
    print(f"硅基流动三模型面板：{asyncio.run(main())}")
