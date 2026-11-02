import asyncio
from types import SimpleNamespace

import pytest
from mcp import Client

from merchant_agent.mcp_server import create_server
from merchant_agent.tools.search.fake_search import FakeSearchProvider
from merchant_agent.tools.search.search_result import SearchResult
from merchant_agent.tracing.observed_search import search_web_observed
from merchant_agent.tracing.reader import read_spans


def _call(client, trace_path, query="商家", operation_id="search-1", attempt=1):
    return search_web_observed(
        client, query, 2, trace_path=str(trace_path), trace_id="a" * 32,
        parent_span_id="b" * 16, operation_id=operation_id, attempt=attempt,
    )


def test_real_mcp_search_keeps_evidence_snapshot(tmp_path):
    result = SearchResult("商家指南", "https://example.com/guide", "商家经营建议",
                          "2026-11-01T00:00:00Z", "fake")
    provider = FakeSearchProvider([result])
    trace_path = tmp_path / "trace.jsonl"

    async def run():
        async with Client(create_server("unused.db", search_provider=provider)) as client:
            found = await _call(client, trace_path)
            empty = await _call(client, trace_path, "无匹配", operation_id="search-2")
            assert len(found["results"]) == 1
            assert empty["results"] == []

    asyncio.run(run())
    first, second = read_spans(str(trace_path))
    assert first["attributes"]["outcome"] == "success"
    assert first["attributes"]["arguments"] == {"query": "商家", "limit": 2}
    assert first["attributes"]["search_snapshot"]["results"][0]["url"] == result.url
    assert second["attributes"]["outcome"] == "empty_result"
    assert second["attributes"]["search_snapshot"]["results"] == []


class FakeClient:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error

    async def call_tool(self, name, arguments):
        if self.error:
            raise self.error
        return self.response


@pytest.mark.parametrize("client, outcome, raw_status", [
    (FakeClient(SimpleNamespace(is_error=True, structured_content=None)), "dependency_error", "mcp_error"),
    (FakeClient(SimpleNamespace(is_error=False, structured_content={"query": "商家"})), "dependency_error", "protocol_error"),
    (FakeClient(error=asyncio.TimeoutError()), "timeout", "timeout"),
])
def test_failed_search_keeps_failure_span(tmp_path, client, outcome, raw_status):
    trace_path = tmp_path / "trace.jsonl"
    with pytest.raises((RuntimeError, asyncio.TimeoutError)):
        asyncio.run(_call(client, trace_path))
    (span,) = read_spans(str(trace_path))
    assert span["attributes"]["outcome"] == outcome
    assert span["attributes"]["raw_status"] == raw_status
    assert "search_snapshot" not in span["attributes"]
