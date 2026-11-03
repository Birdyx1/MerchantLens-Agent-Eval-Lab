"""GLM Markdown 格式诊断：只改变“是否显式禁止代码块”这一条提示。"""

import asyncio
import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from merchant_agent.agent.siliconflow_chat_model import SiliconFlowChatModel
from merchant_agent.evaluation.live_multi_tool_selection import (
    REPEATS,
    ROOT,
    SCORER_PATH,
    _attempt_record,
    _glm_config,
)
from merchant_agent.evaluation.multi_tool_selection import (
    build_messages,
    build_report,
    criteria_sha256,
    input_fingerprint,
    load_cases,
    summarize_results,
)
from merchant_agent.evaluation.pilot_repeated_live import _save


DIAGNOSTIC_INSTRUCTION = (
    "你是商家经营分析 Agent 的规划器。可用工具：\n"
    "get_store_net(store_id)：查询单个虚构门店的净收入（分），store_id 是字符串。\n"
    "search_web(query, limit)：检索网页，query 是字符串，limit 是 1~10 的整数。\n"
    "execute_python(code, timeout_seconds)：在沙箱执行 Python，code 是字符串，"
    "timeout_seconds 是 1~5 的整数。\n"
    "只输出一个 JSON 对象。顶层字段必须为 plan 和 action。\n"
    "plan 是 1~5 条简短步骤；action 必须是 "
    "{\"type\":\"tool\",\"name\":\"工具名\",\"arguments\":{...}}，type 固定为 tool。"
    "不要输出其他内容。"
)


async def main() -> Path:
    """GLM 用同一题集、接口和解码参数运行；只移除显式 Markdown 禁令。"""
    raw, cases = load_cases()
    glm_key, glm_name = _glm_config()
    spec = {
        "key": "glm", "label": "GLM（无显式 Markdown 禁令）", "provider": "siliconflow",
        "interface": "chat_completions",
        "endpoint": "https://api.siliconflow.cn/v1/chat/completions",
        "model_id": glm_name,
        "parameters": {"temperature": 0.0, "top_p": 1.0, "timeout_seconds": 90.0,
                       "json_mode": False, "enable_thinking": None},
    }
    client = SiliconFlowChatModel(glm_name, glm_key, timeout_seconds=90.0,
                                  temperature=0.0, top_p=1.0)
    directory = ROOT / "runs/multi_tool_selection" / uuid.uuid4().hex
    directory.mkdir(parents=True, exist_ok=False, mode=0o700)
    target = directory / "diagnostic_markdown.json"
    record = {
        "status": "running", "run_id": directory.name,
        "started_at": datetime.now(timezone.utc).isoformat(), "ended_at": None,
        "variant": "no_explicit_markdown_ban",
        "fixture": "fixtures/multi_tool_selection_v1.json",
        "fixture_sha256": hashlib.sha256(raw).hexdigest(),
        "instruction": DIAGNOSTIC_INSTRUCTION,
        "instruction_sha256": hashlib.sha256(DIAGNOSTIC_INSTRUCTION.encode("utf-8")).hexdigest(),
        "input_sha256": input_fingerprint(raw, DIAGNOSTIC_INSTRUCTION),
        "scorer_source_sha256": hashlib.sha256(SCORER_PATH.read_bytes()).hexdigest(),
        "repeats": REPEATS, "holdout_used": False, "models": [spec],
        "cases": [{"id": case["id"], "scenario": case["scenario"],
                   "criteria_sha256": criteria_sha256(case)} for case in cases],
        "results": [],
    }
    _save(target, record)
    try:
        for repeat_index in range(REPEATS):
            for case in cases:
                try:
                    response = await client.generate(
                        build_messages(case, DIAGNOSTIC_INSTRUCTION))
                    entry = _attempt_record(spec, case, repeat_index, response=response)
                except Exception as exc:
                    entry = _attempt_record(spec, case, repeat_index, error=exc)
                record["results"].append(entry)
                _save(target, record)
        record["summary"] = summarize_results(record)
        report = build_report(record)
        report_path = directory / "diagnostic_markdown.md"
        report_path.write_text(report, encoding="utf-8")
        os.chmod(report_path, 0o600)
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
    print(f"GLM Markdown 诊断记录：{asyncio.run(main())}")
