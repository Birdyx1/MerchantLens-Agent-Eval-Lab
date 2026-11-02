"""用本地 DeepSeek 配置运行一次基座准入并私有落盘。"""

import asyncio
import json
import os
import uuid
from pathlib import Path

from merchant_agent.agent.deepseek_responses_model import DeepSeekResponsesModel
from merchant_agent.evaluation.base_admission import run_base_admission


ROOT = Path(__file__).resolve().parents[3]


def _config() -> tuple[str, str]:
    """只读取所需键；不执行环境文件内容，也不回显密钥。"""
    values = {}
    path = ROOT / ".env"
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition("=")
            if separator and key.strip() in {"DEEPSEEK_API_KEY", "DEEPSEEK_MODEL"}:
                values[key.strip()] = value.strip().strip("\"'")
    key = os.environ.get("DEEPSEEK_API_KEY") or values.get("DEEPSEEK_API_KEY")
    model = os.environ.get("DEEPSEEK_MODEL") or values.get("DEEPSEEK_MODEL")
    if not key or not model:
        raise RuntimeError("缺少 DeepSeek API Key 或模型名")
    return key, model


async def main() -> Path:
    """执行三道基座探针；每次生成独立私有记录。"""
    key, model_name = _config()
    result = await run_base_admission(DeepSeekResponsesModel(model_name, key))
    directory = ROOT / "runs" / "base_admission"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    destination = directory / f"{uuid.uuid4().hex}.json"
    payload = json.dumps(result, ensure_ascii=False, indent=2).encode("utf-8")
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as output:
        output.write(payload)
        output.flush()
        os.fsync(output.fileno())
    return destination


if __name__ == "__main__":
    path = asyncio.run(main())
    print(f"准入记录：{path}")
