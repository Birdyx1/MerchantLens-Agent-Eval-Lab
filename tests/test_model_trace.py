import asyncio
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from merchant_agent.agent.graph import build_observation_loop_graph
from merchant_agent.agent.model_port import ModelResponse
from merchant_agent.agent.runner import run_agent
from merchant_agent.agent.state import initial_state
from merchant_agent.tracing.reader import read_spans
from merchant_agent.tracing.validator import validate_trace


def _state():
    return initial_state("task-1", "a" * 32, "b" * 16, "问题")


async def _unused_tool(state):
    raise AssertionError("工具不应执行")


def _spans(path):
    spans = read_spans(str(path))
    schema = json.loads((Path(__file__).resolve().parents[1] / "schemas/span.schema.json").read_text())
    assert all(Draft202012Validator(schema).is_valid(span) for span in spans)
    assert validate_trace(spans) == []
    return spans


def test_model_span_has_output_and_root_link(tmp_path):
    response_text = json.dumps({"plan": [], "action": {"type": "finish", "answer": "完成"}})

    class Model:
        async def generate(self, messages):
            return ModelResponse(response_text, "fixed-model", 3, 2)

    path = tmp_path / "trace.jsonl"
    graph = build_observation_loop_graph(Model(), _unused_tool, trace_path=str(path))
    result = asyncio.run(run_agent(graph, _state(), trace_path=str(path)))
    assert result["final_answer"] == "完成"
    model_span, root_span = _spans(path)
    assert model_span["name"] == "model.plan"
    assert model_span["parent_span_id"] == root_span["span_id"]
    assert model_span["attributes"]["model_output"] == response_text
    assert model_span["attributes"]["model_id"] == "fixed-model"
    assert model_span["attributes"]["input_tokens"] == 3
    assert model_span["attributes"]["output_tokens"] == 2


@pytest.mark.parametrize("response_text,error_type", [
    ("bad-json", "ValueError"),
])
def test_invalid_model_output_is_still_traced(tmp_path, response_text, error_type):
    class Model:
        async def generate(self, messages):
            return ModelResponse(response_text, "fixed-model", 1, 1)

    path = tmp_path / "trace.jsonl"
    graph = build_observation_loop_graph(Model(), _unused_tool, trace_path=str(path))
    with pytest.raises(ValueError):
        asyncio.run(run_agent(graph, _state(), trace_path=str(path)))
    model_span, root_span = _spans(path)
    assert model_span["attributes"]["model_output"] == response_text
    assert model_span["attributes"]["error_type"] == error_type
    assert root_span["attributes"]["termination_reason"] == "error"
