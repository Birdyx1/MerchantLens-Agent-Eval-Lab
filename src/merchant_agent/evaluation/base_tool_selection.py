"""无答案示例的多工具选择探针及确定性评分。"""

import ast
import hashlib
import json
from pathlib import Path

from merchant_agent.agent.planning import parse_planning_decision


ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "fixtures/base_tool_selection_v1.json"
INSTRUCTION = (
    "你可选择以下工具：get_store_net(store_id) 查询门店净收入；"
    "search_web(query,limit) 检索网页；execute_python(code,timeout_seconds) 执行 Python。"
    "仅输出 JSON 对象，顶层字段为 plan（字符串数组）和 action；"
    "action 包含 type、name、arguments，type 固定为 tool。不要输出其他内容。"
)


def load_cases() -> tuple[bytes, list[dict]]:
    raw = FIXTURE.read_bytes()
    fixture = json.loads(raw)
    cases = fixture["cases"]
    if fixture.get("version") != "1.0" or len(cases) != 4 or len({x["id"] for x in cases}) != 4:
        raise ValueError("探针集结构无效")
    return raw, cases


def score_selection(case: dict, output: str) -> dict:
    """分开记录输出契约、工具选择和参数；Python 仅解析 AST 不执行。"""
    try:
        decision = parse_planning_decision(output)
    except ValueError:
        return {"contract": False, "tool_correct": None, "arguments_correct": None, "passed": False}
    tool_correct = decision.tool_name == case["expected_tool"]
    args_correct = decision.tool_arguments == case["expected_arguments"]
    if tool_correct and case["expected_tool"] == "execute_python":
        args = decision.tool_arguments or {}
        try:
            args_correct = (args.get("timeout_seconds") == 2 and
                            ast.dump(ast.parse(args.get("code", ""))) == ast.dump(ast.parse("print(6*7)")))
        except (SyntaxError, ValueError, TypeError):
            args_correct = False
    return {"contract": True, "tool_correct": tool_correct,
            "arguments_correct": bool(tool_correct and args_correct),
            "passed": bool(tool_correct and args_correct)}


def input_fingerprint(raw: bytes) -> str:
    """绑定探针和公开工具契约，期望字段不会发往模型。"""
    return hashlib.sha256(raw + INSTRUCTION.encode()).hexdigest()
