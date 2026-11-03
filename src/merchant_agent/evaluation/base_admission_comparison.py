"""同一组公开合成探针对两个基座做直接调用，不运行 Harness。"""

import asyncio
import hashlib
import uuid
from dataclasses import asdict
from pathlib import Path
import json

from merchant_agent.agent.deepseek_responses_model import DeepSeekResponsesModel
from merchant_agent.agent.siliconflow_chat_model import SiliconFlowChatModel
from merchant_agent.evaluation.base_admission import PROBES, run_base_admission
from merchant_agent.evaluation.base_admission_live import _config as deepseek_config
from merchant_agent.evaluation.live_siliconflow_panel_challenges import _config as siliconflow_config
from merchant_agent.evaluation.pilot_repeated_live import _save


ROOT = Path(__file__).resolve().parents[3]


async def main() -> Path:
    """固定输入及评分源码；每模型每题只运行一次，不筛选结果。"""
    deepseek_key, deepseek_name = deepseek_config()
    siliconflow_key, siliconflow_models = siliconflow_config()
    models = ((deepseek_name, DeepSeekResponsesModel(deepseek_name, deepseek_key)),
              (siliconflow_models[0], SiliconFlowChatModel(siliconflow_models[0], siliconflow_key)))
    probe_bytes = json.dumps([asdict(probe) for probe in PROBES], ensure_ascii=False,
                             sort_keys=True).encode()
    directory = ROOT / "runs/base_admission_comparison" / uuid.uuid4().hex
    directory.mkdir(parents=True, exist_ok=False, mode=0o700)
    target = directory / "results.json"
    record = {"status": "running", "probe_sha256": hashlib.sha256(probe_bytes).hexdigest(),
              "scorer_sha256": hashlib.sha256((ROOT / "src/merchant_agent/evaluation/base_admission.py").read_bytes()).hexdigest(),
              "scope": "公开合成探针，直接调用模型，每题一次", "holdout_used": False,
              "model_parameters": "两者均使用各自服务默认解码参数", "results": []}
    _save(target, record)
    try:
        for model_name, model in models:
            result = await run_base_admission(model)
            record["results"].append({"configured_model": model_name, **result})
            _save(target, record)
        record["status"] = "completed"
    except BaseException as exc:
        record["status"] = "failed"
        record["error_type"] = type(exc).__name__
        raise
    finally:
        _save(target, record)
    return target


if __name__ == "__main__":
    print(f"基座准入对照记录：{asyncio.run(main())}")
