import asyncio
import json

from merchant_agent.agent.model_port import ModelResponse
from merchant_agent.evaluation.base_admission import PROBES, run_base_admission, score_probe


class ProbeModel:
    def __init__(self, outputs):
        self.outputs = iter(outputs)
        self.calls = []

    async def generate(self, messages):
        self.calls.append(messages)
        return ModelResponse(next(self.outputs), "base-test", 10, 4)


def test_all_three_direct_model_probes_pass():
    model = ProbeModel([
        json.dumps({"plan": ["查询"], "action": {"type": "tool", "name": "get_store_net",
                                                "arguments": {"store_id": "A"}}}),
        '{"status":"ready"}',
        "paid_fen - refunded_fen",
    ])
    result = asyncio.run(run_base_admission(model))
    assert result["passed"] is True
    assert len(model.calls) == 3
    assert result["scope"] == "direct_model_no_harness_or_tools"


def test_code_probe_rejects_unsafe_or_wrong_expression():
    probe = PROBES[2]
    assert score_probe(probe, "paid_fen + refunded_fen")[0] is False
    assert score_probe(probe, '__import__("os").system("echo bad")')[0] is False
    assert score_probe(probe, "paid_fen - refunded_fen")[0] is True


def test_tool_probe_rejects_wrong_route_and_call_failure_is_recorded():
    wrong = json.dumps({"plan": [], "action": {"type": "tool", "name": "get_store_net",
                                              "arguments": {"store_id": "B"}}})
    assert score_probe(PROBES[0], wrong)[0] is False
    result = asyncio.run(run_base_admission(ProbeModel([wrong, "not-json", "paid_fen"])))
    assert result["passed"] is False
    assert [row["passed"] for row in result["probes"]] == [False, False, False]
