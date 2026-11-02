from merchant_agent.tracing.writer import append_span


def test_trace_file_is_private_and_append_preserves_records(tmp_path):
    path = tmp_path / "nested" / "trace.jsonl"
    append_span(str(path), {"n": 1})
    append_span(str(path), {"n": 2})
    assert path.stat().st_mode & 0o777 == 0o600
    assert path.read_text(encoding="utf-8").splitlines() == ['{"n": 1}', '{"n": 2}']
