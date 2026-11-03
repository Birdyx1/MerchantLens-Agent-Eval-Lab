"""固定模型端口，仅替换规划提示词；成对汇总拒绝缺格。"""

import asyncio
import json

import pytest

from merchant_agent.agent.model_port import ModelResponse
from merchant_agent.agent.planning import make_plan_node
from merchant_agent.agent.state import initial_state
from merchant_agent.evaluation.prompt_harness_experiment import summarize_pairs


class CaptureModel:
    async def generate(self, messages):
        self.messages = messages
        return ModelResponse(json.dumps({"plan": [], "action": {"type": "finish", "answer": "完成"}}),
                             "same-model", 1, 1)


def test_planning_instruction_is_injected_without_changing_state_contract():
    model = CaptureModel()
    state = initial_state("task", "a" * 32, "b" * 16, "请求")
    update = asyncio.run(make_plan_node(model, planning_instruction="固定的候选指令")(state))
    assert model.messages[0] == {"role": "system", "content": "固定的候选指令"}
    assert update["final_answer"] == "完成"


def test_paired_summary_reports_discordant_pairs():
    items = [{"pair_index": 0, "arm": "baseline", "passed": False},
             {"pair_index": 0, "arm": "explicit_json_after_tool", "passed": True},
             {"pair_index": 1, "arm": "baseline", "passed": True},
             {"pair_index": 1, "arm": "explicit_json_after_tool", "passed": True}]
    summary = summarize_pairs(items, pairs=2)
    assert summary["delta_rate"] == 0.5
    assert summary["candidate_only_success_pairs"] == 1
    with pytest.raises(ValueError):
        summarize_pairs(items[:-1], pairs=2)
