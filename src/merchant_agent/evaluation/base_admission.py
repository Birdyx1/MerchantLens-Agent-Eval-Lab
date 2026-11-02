"""绕过 Harness 的基座模型能力准入探针。"""

import ast
import json
from dataclasses import dataclass

from merchant_agent.agent.model_port import ModelPort
from merchant_agent.agent.planning import parse_planning_decision


@dataclass(frozen=True, slots=True)
class AdmissionProbe:
    probe_id: str
    dimension: str
    instruction: str
    user_input: str


PROBES = (
    AdmissionProbe("tool_route", "tool_call", (
        '只输出 JSON 对象，格式为 {"plan":["简短步骤"],"action":'
        '{"type":"tool","name":"get_store_net","arguments":{"store_id":"A"}}}。'
        "不要 Markdown 或额外文字。"
    ),
                   "请查询 A 门店的净收入。"),
    AdmissionProbe("strict_json", "instruction", '只输出 JSON 对象 {"status":"ready"}，不要额外文字。',
                   "请确认准备就绪。"),
    AdmissionProbe("net_expression", "code", "只输出一个 Python 表达式，使用 paid_fen 与 refunded_fen 计算净收入；不要代码块。",
                   "净收入等于已支付金额减去退款金额。"),
)


def _eval_expression(text: str, paid: int, refunded: int) -> int:
    """仅解释整数、两个变量与加减乘运算，不执行模型生成的代码。"""
    node = ast.parse(text, mode="eval").body
    def visit(item):
        if isinstance(item, ast.Name) and item.id in {"paid_fen", "refunded_fen"}:
            return paid if item.id == "paid_fen" else refunded
        if isinstance(item, ast.Constant) and type(item.value) is int:
            return item.value
        if isinstance(item, ast.BinOp) and type(item.op) in {ast.Add, ast.Sub, ast.Mult}:
            left, right = visit(item.left), visit(item.right)
            return left + right if isinstance(item.op, ast.Add) else (
                left - right if isinstance(item.op, ast.Sub) else left * right
            )
        raise ValueError("代码表达式包含不允许的语法")
    return visit(node)


def score_probe(probe: AdmissionProbe, text: str) -> tuple[bool, str]:
    """对三类输出分别做确定性校验，不用 LLM 自评。"""
    try:
        if probe.probe_id == "tool_route":
            decision = parse_planning_decision(text)
            passed = decision.tool_name == "get_store_net" and decision.tool_arguments == {"store_id": "A"}
        elif probe.probe_id == "strict_json":
            passed = json.loads(text) == {"status": "ready"} and isinstance(json.loads(text), dict)
        elif probe.probe_id == "net_expression":
            vectors = ((15000, 3000), (500, 700), (0, 0), (87, 13))
            passed = all(_eval_expression(text, paid, refunded) == paid - refunded
                         for paid, refunded in vectors)
        else:
            raise ValueError("未知准入探针")
    except (ValueError, SyntaxError, TypeError, RecursionError):
        return False, "输出结构或语义不符合准入契约"
    return passed, "通过" if passed else "输出语义不符合预期"


async def run_base_admission(model: ModelPort) -> dict:
    """直接调用模型，每道探针一次；保留原始输出和用量供归因。"""
    records = []
    for probe in PROBES:
        try:
            response = await model.generate([
                {"role": "system", "content": probe.instruction},
                {"role": "user", "content": probe.user_input},
            ])
            passed, reason = score_probe(probe, response.text)
            records.append({"probe_id": probe.probe_id, "dimension": probe.dimension,
                            "passed": passed, "reason": reason, "model_id": response.model_id,
                            "output": response.text, "input_tokens": response.input_tokens,
                            "output_tokens": response.output_tokens})
        except Exception as exc:
            records.append({"probe_id": probe.probe_id, "dimension": probe.dimension,
                            "passed": False, "reason": f"模型调用失败：{type(exc).__name__}",
                            "model_id": None, "output": None,
                            "input_tokens": None, "output_tokens": None})
    return {"passed": all(item["passed"] for item in records), "probes": records,
            "scope": "direct_model_no_harness_or_tools"}
