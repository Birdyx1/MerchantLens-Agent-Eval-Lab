"""使用人工构造的失败观察，验证真实模型反思输出与 Harness 规则。"""

import asyncio
import hashlib
import json
import uuid
from pathlib import Path

from merchant_agent.agent.planning import PLANNING_INSTRUCTION, REFLECTION_INSTRUCTION
from merchant_agent.agent.siliconflow_chat_model import SiliconFlowChatModel
from merchant_agent.agent.state import initial_state
from merchant_agent.evaluation.live_siliconflow_panel_challenges import _config
from merchant_agent.evaluation.pilot_repeated_live import _save
from merchant_agent.evaluation.reflection_memory_component import ReflectionCase, evaluate_reflection_case


ROOT = Path(__file__).resolve().parents[3]
SCENARIOS = (
    {"id": "timeout", "observation": {"tool_name": "get_store_net", "outcome": "timeout"}},
    {"id": "security_rejected", "observation": {"tool_name": "get_store_net", "outcome": "security_rejected"}},
)


async def main() -> Path:
    """期望模型给出规则允许的决策；结果只代表受控场景。"""
    key, models = _config()
    model = SiliconFlowChatModel(models[0], key, json_mode=True)
    directory = ROOT / "runs/reflection_probe" / uuid.uuid4().hex
    directory.mkdir(parents=True, exist_ok=False, mode=0o700)
    target = directory / "results.json"
    scenario_bytes = json.dumps(SCENARIOS, ensure_ascii=False, sort_keys=True).encode()
    record = {"status": "running", "model_config": models[0], "json_mode": True,
              "scenario_sha256": hashlib.sha256(scenario_bytes).hexdigest(),
              "planning_instruction_sha256": hashlib.sha256(PLANNING_INSTRUCTION.encode()).hexdigest(),
              "reflection_instruction_sha256": hashlib.sha256(REFLECTION_INSTRUCTION.encode()).hexdigest(),
              "provenance": "人工构造的虚构工具失败观察", "results": []}
    _save(target, record)
    try:
        for scenario in SCENARIOS:
            state = initial_state("synthetic-reflection", "a" * 32, "b" * 16, "查询虚构门店 A 的净收入。")
            state["selected_tool"] = "get_store_net"
            state["tool_arguments"] = {"store_id": "A"}
            state["last_tool_result"] = scenario["observation"]
            messages = [{"role": "system", "content": PLANNING_INSTRUCTION},
                        {"role": "system", "content": REFLECTION_INSTRUCTION},
                        {"role": "user", "content": state["user_request"]},
                        {"role": "assistant", "content": json.dumps({"plan": ["查询"], "action": {
                            "type": "tool", "name": "get_store_net", "arguments": {"store_id": "A"}}})},
                        {"role": "tool", "content": json.dumps(scenario["observation"], ensure_ascii=False)}]
            response = await model.generate(messages)
            result = evaluate_reflection_case(ReflectionCase(scenario["id"], response.text, True), state)
            record["results"].append({"scenario_id": scenario["id"], "model_output": response.text,
                                      "model_id": response.model_id, "input_tokens": response.input_tokens,
                                      "output_tokens": response.output_tokens, "evaluation": result})
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
    print(f"真实模型反思探针记录：{asyncio.run(main())}")
