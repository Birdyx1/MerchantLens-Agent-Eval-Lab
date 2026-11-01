def validate_trace(spans: list[dict]) -> list[str]:
    span_id_set = set()
    trace_id_set = set()
    rs = []
    for span in spans:
        trace_id_set.add(span['trace_id'])
        span_id_set.add(span['span_id'])

    if len(trace_id_set) > 1:
        rs.append("mixed_trace_id")
    if len(span_id_set) < len(spans):
        rs.append("duplicate_span_id")
    return rs
