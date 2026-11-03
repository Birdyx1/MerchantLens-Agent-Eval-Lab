"""脱敏、去重与来源标记：把异常证据整理成可回流的样本。"""

import copy
import re


_SENSITIVE_PATTERNS = (
    (re.compile(r"sk-[A-Za-z0-9]{8,}"), "[REDACTED_KEY]"),
    (re.compile(r"\b1[3-9]\d{9}\b"), "[REDACTED_PHONE]"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "[REDACTED_EMAIL]"),
)


def sanitize_text(text):
    """掩码密钥、手机号与邮箱；非字符串原样返回。"""
    if not isinstance(text, str):
        return text
    for pattern, replacement in _SENSITIVE_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def _sanitize_value(value):
    if isinstance(value, str):
        return sanitize_text(value)
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _sanitize_value(item) for key, item in value.items()}
    return value


def sanitize_trial(trial: dict, spans: list[dict]) -> tuple[dict, list[dict]]:
    """返回脱敏后的副本，不修改原对象。"""
    return _sanitize_value(copy.deepcopy(trial)), _sanitize_value(copy.deepcopy(spans))


def deduplicate(findings: list[dict]) -> list[dict]:
    """按 (task_id, 异常类型集合) 去重；保留首条并记录重复次数。"""
    seen: dict[tuple, dict] = {}
    for finding in findings:
        types = tuple(sorted({anomaly["type"] for anomaly in finding["anomalies"]}))
        key = (finding.get("task_id"), types)
        if key in seen:
            seen[key]["duplicates"] += 1
            continue
        seen[key] = {**finding, "duplicates": 1}
    return list(seen.values())


def tag_source(finding: dict, *, source: str) -> dict:
    """标注样本来源：synthetic / production_badcase / adversarial。"""
    if source not in {"synthetic", "production_badcase", "adversarial"}:
        raise ValueError("未知来源")
    return {**finding, "source": source}
