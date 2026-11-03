"""对冻结多工具选择探针运行双模型对照。"""

import asyncio
import hashlib
import uuid
from pathlib import Path

from merchant_agent.agent.deepseek_responses_model import DeepSeekResponsesModel
from merchant_agent.agent.siliconflow_chat_model import SiliconFlowChatModel
from merchant_agent.evaluation.base_admission_live import _config as deepseek_config
from merchant_agent.evaluation.base_tool_selection import INSTRUCTION, input_fingerprint, load_cases, score_selection
from merchant_agent.evaluation.live_siliconflow_panel_challenges import _config as siliconflow_config
from merchant_agent.evaluation.pilot_repeated_live import _save


ROOT = Path(__file__).resolve().parents[3]


async def main() -> Path:
    """每模型每题一次；失败与输出保留，禁止挑选成功结果。"""
    raw, cases = load_cases()
    dk, dn = deepseek_config()
    sk, sm = siliconflow_config()
    models = ((dn, DeepSeekResponsesModel(dn, dk)), (sm[0], SiliconFlowChatModel(sm[0], sk)))
    directory = ROOT / "runs/base_tool_selection" / uuid.uuid4().hex
    directory.mkdir(parents=True, exist_ok=False, mode=0o700)
    path = directory / "results.json"
    record = {"status": "running", "fixture_sha256": hashlib.sha256(raw).hexdigest(),
              "input_sha256": input_fingerprint(raw),
              "scorer_sha256": hashlib.sha256((ROOT / "src/merchant_agent/evaluation/base_tool_selection.py").read_bytes()).hexdigest(),
              "models": [name for name, _ in models], "holdout_used": False, "results": []}
    _save(path, record)
    try:
        for model_name, model in models:
            for case in cases:
                try:
                    response = await model.generate([{"role": "system", "content": INSTRUCTION},
                                                     {"role": "user", "content": case["input"]}])
                    result = {"model": model_name, "case_id": case["id"], "status": "scored",
                              "model_id": response.model_id, "output": response.text,
                              "input_tokens": response.input_tokens, "output_tokens": response.output_tokens,
                              "score": score_selection(case, response.text)}
                except Exception as exc:
                    result = {"model": model_name, "case_id": case["id"], "status": "error",
                              "error_type": type(exc).__name__, "score": None}
                record["results"].append(result)
                _save(path, record)
        record["status"] = "completed"
    except BaseException as exc:
        record["status"] = "failed"
        record["error_type"] = type(exc).__name__
        raise
    finally:
        _save(path, record)
    return path


if __name__ == "__main__":
    print(f"基座工具选择探针记录：{asyncio.run(main())}")
