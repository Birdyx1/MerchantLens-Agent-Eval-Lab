import json

def read_spans(path:str) -> list[dict]:
    """
    要求：读取 UTF-8 JSONL 文件，逐行解析，按原顺序返回 Span 列表。可以使用 Python 标准库的 open 和 json.loads。
    """
    rs = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            span = json.loads(line)
            rs.append(span)
    return rs
