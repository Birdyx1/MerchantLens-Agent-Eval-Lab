"""在冻结多工具选择题集上运行 DeepSeek 与 GLM，保留全部输出和失败。"""

import asyncio
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from merchant_agent.agent.deepseek_responses_model import DeepSeekResponsesModel
from merchant_agent.agent.siliconflow_chat_model import SiliconFlowChatModel
from merchant_agent.evaluation.base_admission_live import _config as deepseek_config
from merchant_agent.evaluation.multi_tool_selection import (
    INSTRUCTION,
    build_messages,
    build_report,
    criteria_sha256,
    input_fingerprint,
    load_cases,
    score_selection,
    summarize_results,
)
from merchant_agent.evaluation.pilot_repeated_live import _save


ROOT = Path(__file__).resolve().parents[3]
REPEATS = 2
SCORER_PATH = ROOT / "src/merchant_agent/evaluation/multi_tool_selection.py"
RUNNER_PATH = ROOT / "src/merchant_agent/evaluation/live_multi_tool_selection.py"


def _glm_config() -> tuple[str, str]:
    """只读取硅基流动的 Key 与第一个模型名，不打印或保存密钥。"""
    values = {}
    wanted = {"SILICONFLOW_API_KEY", "SILICONFLOW_JUDGE_MODEL_1"}
    path = ROOT / ".env"
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition("=")
            if separator and key.strip() in wanted:
                values[key.strip()] = value.strip().strip("\"'")
    key = os.environ.get("SILICONFLOW_API_KEY") or values.get("SILICONFLOW_API_KEY")
    model = os.environ.get("SILICONFLOW_JUDGE_MODEL_1") or values.get("SILICONFLOW_JUDGE_MODEL_1")
    if not key or not model:
        raise RuntimeError("缺少硅基流动 API Key 或模型名")
    return key, model


def _model_specs() -> tuple[list[dict], dict]:
    """固定每个模型的接口、超时和解码参数，供重复运行复用。"""
    deepseek_key, deepseek_name = deepseek_config()
    glm_key, glm_name = _glm_config()
    specs = [
        {
            "key": "deepseek", "label": "DeepSeek", "provider": "deepseek",
            "interface": "responses", "endpoint": "https://api.deepseek.com/responses",
            "model_id": deepseek_name,
            "parameters": {"temperature": 0.0, "top_p": None, "timeout_seconds": 60.0,
                           "json_mode": False, "enable_thinking": None},
        },
        {
            "key": "glm", "label": "GLM", "provider": "siliconflow",
            "interface": "chat_completions",
            "endpoint": "https://api.siliconflow.cn/v1/chat/completions",
            "model_id": glm_name,
            "parameters": {"temperature": 0.0, "top_p": 1.0, "timeout_seconds": 90.0,
                           "json_mode": False, "enable_thinking": None},
        },
    ]
    clients = {
        "deepseek": DeepSeekResponsesModel(
            deepseek_name, deepseek_key, timeout_seconds=60.0, temperature=0.0),
        "glm": SiliconFlowChatModel(
            glm_name, glm_key, timeout_seconds=90.0, temperature=0.0, top_p=1.0),
    }
    return specs, clients


def _attempt_record(spec: dict, case: dict, repeat_index: int, response=None,
                    error: BaseException | None = None) -> dict:
    if error is not None:
        return {
            "model": spec["key"], "case_id": case["id"], "repeat_index": repeat_index,
            "status": "error", "model_id": None, "output": None,
            "input_tokens": None, "output_tokens": None,
            "error_type": type(error).__name__, "error_message": str(error)[:500],
            "score": {"contract": None, "format_kind": "call_error",
                      "tool_correct": None, "arguments_correct": None,
                      "passed": False, "failure_type": "call_error", "recovered": None},
        }
    return {
        "model": spec["key"], "case_id": case["id"], "repeat_index": repeat_index,
        "status": "scored", "model_id": response.model_id, "output": response.text,
        "input_tokens": response.input_tokens, "output_tokens": response.output_tokens,
        "error_type": None, "error_message": None,
        "score": score_selection(case, response.text),
    }


async def main() -> Path:
    """每模型每题重复两次；任何失败都落盘，不重试到通过后只报最好结果。"""
    raw, cases = load_cases()
    specs, clients = _model_specs()
    directory = ROOT / "runs/multi_tool_selection" / uuid.uuid4().hex
    directory.mkdir(parents=True, exist_ok=False, mode=0o700)
    target = directory / "results.json"
    report_path = directory / "report.md"
    record = {
        "status": "running",
        "run_id": directory.name,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "ended_at": None,
        "fixture": "fixtures/multi_tool_selection_v1.json",
        "fixture_sha256": hashlib.sha256(raw).hexdigest(),
        "input_sha256": input_fingerprint(raw),
        "instruction_sha256": hashlib.sha256(INSTRUCTION.encode("utf-8")).hexdigest(),
        "scorer_source_sha256": hashlib.sha256(SCORER_PATH.read_bytes()).hexdigest(),
        "runner_source_sha256": hashlib.sha256(RUNNER_PATH.read_bytes()).hexdigest(),
        "repeats": REPEATS,
        "holdout_used": False,
        "models": specs,
        "cases": [{"id": case["id"], "scenario": case["scenario"],
                   "input": case["input"], "criteria_sha256": criteria_sha256(case)}
                  for case in cases],
        "results": [],
    }
    _save(target, record)
    try:
        for spec in specs:
            client = clients[spec["key"]]
            for repeat_index in range(REPEATS):
                for case in cases:
                    try:
                        response = await client.generate(build_messages(case))
                        entry = _attempt_record(spec, case, repeat_index, response=response)
                    except Exception as exc:
                        entry = _attempt_record(spec, case, repeat_index, error=exc)
                    record["results"].append(entry)
                    _save(target, record)
        record["summary"] = summarize_results(record)
        report = build_report(record)
        report_path.write_text(report, encoding="utf-8")
        os.chmod(report_path, 0o600)
        record["report_path"] = str(report_path.relative_to(ROOT))
        record["status"] = "completed"
    except BaseException as exc:
        record["status"] = "failed"
        record["error_type"] = type(exc).__name__
        raise
    finally:
        record["ended_at"] = datetime.now(timezone.utc).isoformat()
        if "summary" not in record:
            record["summary"] = summarize_results(record)
        _save(target, record)
    return target


if __name__ == "__main__":
    print(f"多工具选择运行记录：{asyncio.run(main())}")
