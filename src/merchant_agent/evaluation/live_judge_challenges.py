"""对人工构造的固定边界回答运行真实清晰度裁判。"""

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
FIXTURE = ROOT / "fixtures/judge_clarity_challenges_v1.json"


async def main() -> Path:
    """冻结挑战集和 Rubric 摘要；设计分数只用于诊断，不冒充人工真值。"""
    raw = FIXTURE.read_bytes()
    fixture = json.loads(raw)
    cases = fixture.get("cases")
    if (fixture.get("schema_version") != "1.0"
            or fixture.get("fixture_id") != "judge_clarity_challenges_v1"
            or not isinstance(cases, list) or len(cases) != 6
            or len({case["case_id"] for case in cases}) != len(cases)
            or {case["designed_score"] for case in cases} != {0, 1, 2}):
        raise ValueError("挑战集契约无效")
    key, model_name = _config()
    model = DeepSeekResponsesModel(model_name, key)
    directory = ROOT / "runs" / "judge_challenges" / uuid.uuid4().hex
    directory.mkdir(parents=True, exist_ok=False, mode=0o700)
    target = directory / "results.json"
    record = {"status": "running", "started_at": datetime.now(timezone.utc).isoformat(),
              "fixture_id": fixture["fixture_id"], "fixture_sha256": hashlib.sha256(raw).hexdigest(),
              "rubric_sha256": hashlib.sha256((ROOT / RUBRIC_PATH).read_bytes()).hexdigest(),
              "judge_source_sha256": hashlib.sha256((ROOT / "src/merchant_agent/evaluation/llm_judge.py").read_bytes()).hexdigest(),
              "judge_model_config": model_name, "provenance": fixture["provenance"],
              "results": []}
    _save(target, record)
    try:
        for case in cases:
            trial_id = f"synthetic-{case['case_id']}"
            task_id = "synthetic_clarity_probe"
            trial = {"trial_id": trial_id, "task_id": task_id, "final_answer": case["answer"]}
            code_score = {"trial_id": trial_id, "task_id": task_id, "passed": False}
            judge = await judge_answer_clarity(trial, code_score, project_root=ROOT, model=model)
            record["results"].append({"case_id": case["case_id"],
                                      "designed_score": case["designed_score"],
                                      "judge": judge})
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
    print(f"边界挑战记录：{asyncio.run(main())}")
