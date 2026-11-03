"""多工具选择评测集：冻结题面、确定性评分、分层汇总与报告。"""

import ast
import hashlib
import json
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "fixtures/multi_tool_selection_v1.json"
TOOL_CONTRACTS = {
    "get_store_net": ("store_id",),
    "search_web": ("query", "limit"),
    "execute_python": ("code", "timeout_seconds"),
}
SCENARIOS = frozenset({"baseline", "wrong_tool", "missing_parameter", "tool_confusion"})
INSTRUCTION = (
    "你是商家经营分析 Agent 的规划器。可用工具：\n"
    "get_store_net(store_id)：查询单个虚构门店的净收入（分），store_id 是字符串。\n"
    "search_web(query, limit)：检索网页，query 是字符串，limit 是 1~10 的整数。\n"
    "execute_python(code, timeout_seconds)：在沙箱执行 Python，code 是字符串，"
    "timeout_seconds 是 1~5 的整数。\n"
    "只输出一个 JSON 对象，不要 Markdown、代码块或额外文字。顶层字段必须为 plan 和 action。\n"
    "plan 是 1~5 条简短步骤；action 必须是 "
    "{\"type\":\"tool\",\"name\":\"工具名\",\"arguments\":{...}}，type 固定为 tool。"
    "不要输出其他内容。"
)


def load_cases() -> tuple[bytes, list[dict]]:
    """读取并校验冻结题集；期望字段只用于评测侧。"""
    raw = FIXTURE.read_bytes()
    fixture = json.loads(raw)
    cases = fixture.get("cases")
    if (fixture.get("fixture_id") != "multi_tool_selection_v1"
            or fixture.get("version") != "1.0"
            or not isinstance(cases, list) or len(cases) < 6):
        raise ValueError("多工具选择题集结构无效")
    if len({case.get("id") for case in cases}) != len(cases):
        raise ValueError("多工具选择题集 ID 重复")
    if not {"wrong_tool", "missing_parameter", "tool_confusion"} <= {
            case.get("scenario") for case in cases}:
        raise ValueError("多工具选择题集未覆盖要求的失败场景")
    for case in cases:
        if (not isinstance(case.get("id"), str) or not case["id"].strip()
                or case.get("scenario") not in SCENARIOS
                or not isinstance(case.get("input"), str) or not case["input"].strip()):
            raise ValueError("多工具选择题面字段无效")
        expected = case.get("expected")
        if (not isinstance(expected, dict) or set(expected) != {"name", "arguments"}
                or expected["name"] not in TOOL_CONTRACTS
                or not isinstance(expected["arguments"], dict)):
            raise ValueError("多工具选择期望动作无效")
        arguments = expected["arguments"]
        if set(arguments) != set(TOOL_CONTRACTS[expected["name"]]):
            raise ValueError("期望参数与公开工具契约不一致")
        if not _valid_expected_arguments(expected["name"], arguments):
            raise ValueError("期望参数取值无效")
    return raw, cases


def _valid_expected_arguments(name: str, arguments: dict) -> bool:
    """用公开工具契约校验期望参数，避免冻结错误的标签。"""
    if name == "get_store_net":
        return isinstance(arguments["store_id"], str) and bool(arguments["store_id"].strip())
    if name == "search_web":
        return (isinstance(arguments["query"], str) and bool(arguments["query"].strip())
                and type(arguments["limit"]) is int and 1 <= arguments["limit"] <= 10)
    return (isinstance(arguments["code"], str) and bool(arguments["code"].strip())
            and type(arguments["timeout_seconds"]) is int
            and 1 <= arguments["timeout_seconds"] <= 5)


def criteria_sha256(case: dict) -> str:
    """把单题题面与期望判据绑定为一个可追溯摘要。"""
    payload = json.dumps(case, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def input_fingerprint(raw: bytes, instruction: str = INSTRUCTION) -> str:
    """绑定冻结题集和公开指令；期望字段不会随指令发往模型。"""
    return hashlib.sha256(raw + instruction.encode("utf-8")).hexdigest()


def build_messages(case: dict, instruction: str = INSTRUCTION) -> list[dict[str, str]]:
    """只发送公开指令和题面；期望动作不进入模型上下文。"""
    return [{"role": "system", "content": instruction},
            {"role": "user", "content": case["input"]}]


def _parse_payload(text: str) -> tuple[object | None, str]:
    """严格 JSON 优先；代码块内容只用于格式诊断，不作为契约通过。"""
    if not isinstance(text, str):
        return None, "invalid_json"
    try:
        return json.loads(text.strip()), "strict_json"
    except (json.JSONDecodeError, TypeError):
        pass
    match = re.search(r"```[ \t]*(?:json)?[ \t]*\r?\n?(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if match is None:
        return None, "invalid_json"
    try:
        return json.loads(match.group(1).strip()), "markdown_fence"
    except (json.JSONDecodeError, TypeError):
        return None, "markdown_fence_invalid"


def _validate_payload(payload: object) -> dict | None:
    """只校验输出契约，不判断工具和参数是否符合期望。"""
    if not isinstance(payload, dict) or set(payload) != {"plan", "action"}:
        return None
    plan = payload["plan"]
    if (not isinstance(plan, list) or not 1 <= len(plan) <= 5
            or any(not isinstance(item, str) or not item.strip() or len(item) > 200
                   for item in plan)):
        return None
    action = payload["action"]
    if (not isinstance(action, dict) or action.get("type") != "tool"
            or set(action) != {"type", "name", "arguments"}):
        return None
    name = action["name"]
    arguments = action["arguments"]
    if not isinstance(name, str) or not name.strip() or not isinstance(arguments, dict):
        return None
    return {"plan": plan, "name": name, "arguments": arguments}


def _ast_equivalent(actual: object, expected: str) -> bool:
    """只比较 Python 语法树，不执行模型生成的代码。"""
    if not isinstance(actual, str) or not actual.strip():
        return False
    try:
        return ast.dump(ast.parse(actual)) == ast.dump(ast.parse(expected))
    except (SyntaxError, ValueError, TypeError, RecursionError):
        return False


def _count_literals(code: str) -> list[str | None] | None:
    """收集字符串 .count 的字面量参数，防止仅打印常量也通过语义检查。"""
    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError, TypeError, RecursionError):
        return None
    literals: list[str | None] = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "count" and len(node.args) == 1
                and not node.keywords):
            argument = node.args[0]
            literals.append(argument.value if isinstance(argument, ast.Constant)
                            and isinstance(argument.value, str) else None)
    return literals


def _eval_expr(node: ast.AST, environment: dict[str, object]) -> object:
    """解释极小 Python 子集；不导入模块，也不调用任意属性。"""
    if isinstance(node, ast.Constant):
        if type(node.value) not in {int, float, str}:
            raise ValueError("不支持的常量")
        return node.value
    if isinstance(node, ast.Name):
        if node.id not in environment:
            raise ValueError("未定义变量")
        return environment[node.id]
    if isinstance(node, ast.BinOp):
        left = _eval_expr(node.left, environment)
        right = _eval_expr(node.right, environment)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        if isinstance(node.op, ast.FloorDiv):
            return left // right
        if isinstance(node.op, ast.Mod):
            return left % right
        raise ValueError("不支持的二元运算")
    if isinstance(node, ast.UnaryOp):
        value = _eval_expr(node.operand, environment)
        if isinstance(node.op, ast.USub):
            return -value
        if isinstance(node.op, ast.UAdd):
            return +value
        raise ValueError("不支持的一元运算")
    if isinstance(node, ast.JoinedStr):
        parts = []
        for item in node.values:
            if isinstance(item, ast.Constant) and isinstance(item.value, str):
                parts.append(item.value)
            elif isinstance(item, ast.FormattedValue) and item.format_spec is None:
                parts.append(str(_eval_expr(item.value, environment)))
            else:
                raise ValueError("不支持的 f-string")
        return "".join(parts)
    if isinstance(node, ast.Call) and not node.keywords:
        if (isinstance(node.func, ast.Attribute) and node.func.attr == "count"
                and len(node.args) == 1):
            base = _eval_expr(node.func.value, environment)
            argument = _eval_expr(node.args[0], environment)
            if isinstance(base, str) and isinstance(argument, str):
                return base.count(argument)
        if isinstance(node.func, ast.Name) and node.func.id == "len" and len(node.args) == 1:
            return len(_eval_expr(node.args[0], environment))
        raise ValueError("不支持的函数调用")
    raise ValueError("不支持的表达式")


def _printed_values(code: str) -> list[list[object]]:
    """执行安全子集并收集 print 的参数；任何未列入语法的语句直接拒绝。"""
    tree = ast.parse(code)
    environment: dict[str, object] = {}
    printed: list[list[object]] = []
    for statement in tree.body:
        if (isinstance(statement, ast.Assign) and len(statement.targets) == 1
                and isinstance(statement.targets[0], ast.Name)):
            environment[statement.targets[0].id] = _eval_expr(statement.value, environment)
        elif (isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name)
              and statement.value is not None):
            environment[statement.target.id] = _eval_expr(statement.value, environment)
        elif (isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call)
              and isinstance(statement.value.func, ast.Name)
              and statement.value.func.id == "print" and not statement.value.keywords):
            printed.append([_eval_expr(item, environment) for item in statement.value.args])
        else:
            raise ValueError("不支持的语句")
    return printed


def _printed_signature(code: str) -> list[int]:
    """把打印内容归一为整数序列；字符串中的数字也参与比较。"""
    integers: list[int] = []
    for call in _printed_values(code):
        for value in call:
            if type(value) is int:
                integers.append(value)
            elif isinstance(value, float) and value.is_integer():
                integers.append(int(value))
            elif isinstance(value, str):
                integers.extend(int(item) for item in re.findall(r"-?\d+", value))
    return integers


def _python_semantically_equivalent(expected: str, actual: str) -> bool:
    """允许变量赋值和 f-string，但要求 .count 字面量及打印整数一致。"""
    expected_literals = _count_literals(expected)
    actual_literals = _count_literals(actual)
    if expected_literals is None or actual_literals is None:
        return False
    if expected_literals != actual_literals:
        return False
    try:
        return _printed_signature(actual) == _printed_signature(expected)
    except (SyntaxError, ValueError, TypeError, ZeroDivisionError, RecursionError):
        return False


def _arguments_match(expected_name: str, expected: dict, actual: dict) -> bool:
    """参数集合、类型和值都一致才通过；整数与布尔不互相放宽。"""
    if set(actual) != set(expected):
        return False
    for key, expected_value in expected.items():
        actual_value = actual[key]
        if type(actual_value) is not type(expected_value):
            return False
        if expected_name == "execute_python" and key == "code":
            if not (_ast_equivalent(actual_value, expected_value)
                    or _python_semantically_equivalent(expected_value, actual_value)):
                return False
        elif actual_value != expected_value:
            return False
    return True


def _score_decision(case: dict, decision: dict) -> tuple[bool, bool | None]:
    expected = case["expected"]
    tool_correct = decision["name"] == expected["name"]
    arguments_correct = None
    if tool_correct:
        arguments_correct = _arguments_match(
            expected["name"], expected["arguments"], decision["arguments"])
    return tool_correct, arguments_correct


def score_selection(case: dict, output: str) -> dict:
    """分开记录契约、工具与参数；解析失败时工具和参数记为未知。"""
    payload, parse_kind = _parse_payload(output)
    decision = _validate_payload(payload) if payload is not None else None
    if parse_kind == "strict_json" and decision is not None:
        tool_correct, arguments_correct = _score_decision(case, decision)
        failure_type = ("passed" if arguments_correct is True
                        else "wrong_tool" if tool_correct is False else "parameter")
        return {
            "contract": True,
            "format_kind": "strict_json",
            "tool_correct": tool_correct,
            "arguments_correct": arguments_correct,
            "passed": bool(tool_correct and arguments_correct is True),
            "failure_type": failure_type,
            "recovered": None,
        }
    if parse_kind == "strict_json":
        format_kind = "contract_shape"
    elif parse_kind == "markdown_fence" and decision is None:
        format_kind = "markdown_fence_invalid"
    else:
        format_kind = parse_kind
    recovered = None
    if parse_kind in {"markdown_fence", "markdown_fence_invalid"} and decision is not None:
        tool_correct, arguments_correct = _score_decision(case, decision)
        recovered = {"tool_correct": tool_correct, "arguments_correct": arguments_correct,
                     "passed": bool(tool_correct and arguments_correct is True)}
    return {
        "contract": False,
        "format_kind": format_kind,
        "tool_correct": None,
        "arguments_correct": None,
        "passed": False,
        "failure_type": "format",
        "recovered": recovered,
    }


def _empty_case_summary() -> dict:
    return {"attempts": 0, "contract_pass": 0, "tool_known": 0, "tool_correct": 0,
            "arguments_known": 0, "arguments_correct": 0, "passed": 0,
            "failure_types": Counter(), "format_kinds": Counter(),
            "markdown_fence": 0, "markdown_recovered_pass": 0}


def _summarize_attempts(attempts: list[dict]) -> dict:
    total = len(attempts)
    contract_pass = tool_known = tool_correct = 0
    arguments_known = arguments_correct = passed = 0
    failure_types: Counter = Counter()
    format_kinds: Counter = Counter()
    markdown_fence = markdown_recovered_pass = 0
    cases: dict[str, dict] = {}
    for attempt in attempts:
        case_id = attempt["case_id"]
        row = cases.setdefault(case_id, _empty_case_summary())
        row["attempts"] += 1
        status = attempt.get("status")
        score = attempt.get("score") or {}
        if status != "scored":
            failure_types["call_error"] += 1
            format_kinds["call_error"] += 1
            row["failure_types"]["call_error"] += 1
            row["format_kinds"]["call_error"] += 1
            continue
        if score.get("contract") is True:
            contract_pass += 1
            row["contract_pass"] += 1
        if score.get("tool_correct") is not None:
            tool_known += 1
            row["tool_known"] += 1
        if score.get("tool_correct") is True:
            tool_correct += 1
            row["tool_correct"] += 1
        if score.get("arguments_correct") is not None:
            arguments_known += 1
            row["arguments_known"] += 1
        if score.get("arguments_correct") is True:
            arguments_correct += 1
            row["arguments_correct"] += 1
        if score.get("passed"):
            passed += 1
            row["passed"] += 1
        failure_type = score.get("failure_type", "format")
        failure_types[failure_type] += 1
        format_kind = score.get("format_kind", "invalid_json")
        format_kinds[format_kind] += 1
        row["failure_types"][failure_type] += 1
        row["format_kinds"][format_kind] += 1
        if format_kind in {"markdown_fence", "markdown_fence_invalid"}:
            markdown_fence += 1
            row["markdown_fence"] += 1
            recovered = score.get("recovered")
            if recovered and recovered.get("passed"):
                markdown_recovered_pass += 1
                row["markdown_recovered_pass"] += 1
    return {
        "total": total,
        "call_errors": failure_types["call_error"],
        "contract_pass": contract_pass,
        "tool_known": tool_known,
        "tool_correct": tool_correct,
        "unknown_tool": total - tool_known,
        "arguments_known": arguments_known,
        "arguments_correct": arguments_correct,
        "unknown_arguments": total - arguments_known,
        "passed": passed,
        "failure_types": dict(failure_types),
        "format_kinds": dict(format_kinds),
        "markdown_fence": markdown_fence,
        "markdown_recovered_pass": markdown_recovered_pass,
        "cases": cases,
    }


def summarize_results(record: dict) -> dict:
    """按模型汇总，不把不同模型或不同题目混成一个比率。"""
    results = record.get("results") or []
    summary = {}
    for spec in record.get("models") or []:
        key = spec["key"]
        summary[key] = _summarize_attempts(
            [item for item in results if item.get("model") == key])
    return {"models": summary}


def _rate(numerator: int, denominator: int) -> str:
    return f"{numerator}/{denominator}"


def _escape_cell(value: object, limit: int = 160) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\r", " ").replace("\n", "\\n").replace("|", "\\|")
    return text[:limit] + ("…" if len(text) > limit else "")


def build_report(record: dict) -> str:
    """由运行记录生成分模型、分失败类型的 Markdown 报告。"""
    summary = record.get("summary") or summarize_results(record)
    labels = {spec["key"]: spec.get("label", spec["key"]) for spec in record.get("models", [])}
    case_meta = {case["id"]: case for case in record.get("cases", [])}
    lines = [
        "# 多工具选择评测集：分模型与分失败类型报告",
        "",
        f"运行记录：`{record.get('run_id', 'unknown')}`  ",
        f"开始：{record.get('started_at')}  ",
        f"题集：`fixtures/multi_tool_selection_v1.json`，"
        f"sha256 `{record.get('fixture_sha256')}`  ",
        f"输入摘要（题集+公开指令）：`{record.get('input_sha256')}`  ",
        f"评分器：`{record.get('scorer_source_sha256')}`  ",
        f"每题重复：{record.get('repeats')} 次；未使用 Holdout。",
        "",
        "## 方法",
        "",
        "模型只收到公开工具定义、JSON 输出契约和题面；期望工具与参数只保存在评测侧。"
        "所有题目、期望判据、评分器与模型配置在运行前冻结摘要，失败与原始输出全部保留。",
        "",
        "三条统计口径彼此独立：",
        "",
        "- **输出契约**：严格 JSON 且顶层结构和 action 字段符合公开契约；Markdown 代码块、"
        "额外文字和结构缺失均为格式失败。",
        "- **工具选择**：仅在契约通过后比较工具名；解析失败的工具记为未知，不误记为选错。",
        "- **参数正确性**：仅在工具选择正确后比较参数；解析失败或工具错误时参数记为未知，"
        "不进入参数正确率分母。",
        "",
        "## 模型与固定配置",
        "",
        "| 键 | 模型 | 供应商 | 接口 | 解码参数 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for spec in record.get("models", []):
        params = spec.get("parameters") or {}
        lines.append(
            f"| {spec['key']} | {spec.get('label', spec['key'])} | {spec.get('provider')} | "
            f"{spec.get('interface')} | `{json.dumps(params, ensure_ascii=False, sort_keys=True)}` |")
    lines.extend([
        "",
        "## 总体结果",
        "",
        "| 模型 | 调用 | 输出契约通过 | 工具选择正确 | 参数正确 | 整题通过 | 工具未知 | 参数未知 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ])
    for spec in record.get("models", []):
        item = summary["models"][spec["key"]]
        lines.append(
            f"| {labels[spec['key']]} | {item['total']} | "
            f"{_rate(item['contract_pass'], item['total'])} | "
            f"{_rate(item['tool_correct'], item['tool_known'])} | "
            f"{_rate(item['arguments_correct'], item['arguments_known'])} | "
            f"{_rate(item['passed'], item['total'])} | "
            f"{item['unknown_tool']} | {item['unknown_arguments']} |")
    lines.extend([
        "",
        "> 工具选择的分母是契约通过次数，参数正确率的分母是工具选择正确次数；"
        "未知数单列，避免把解析失败算成模型选错。",
        "",
        "## 失败类型",
        "",
        "| 模型 | 调用失败 | 格式失败 | 选错工具 | 参数错误 | 通过 |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ])
    for spec in record.get("models", []):
        item = summary["models"][spec["key"]]
        failures = item["failure_types"]
        lines.append(
            f"| {labels[spec['key']]} | {failures.get('call_error', 0)} | "
            f"{failures.get('format', 0)} | {failures.get('wrong_tool', 0)} | "
            f"{failures.get('parameter', 0)} | {failures.get('passed', 0)} |")
    lines.extend([
        "",
        "## 分题结果",
        "",
        "| 模型 | 题目 | 场景 | 通过 | 契约 | 工具 | 参数 |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: |",
    ])
    for spec in record.get("models", []):
        item = summary["models"][spec["key"]]
        for case_id, row in item["cases"].items():
            case = case_meta.get(case_id, {})
            lines.append(
                f"| {labels[spec['key']]} | {case_id} | {case.get('scenario', 'unknown')} | "
                f"{_rate(row['passed'], row['attempts'])} | "
                f"{_rate(row['contract_pass'], row['attempts'])} | "
                f"{_rate(row['tool_correct'], row['tool_known'])} | "
                f"{_rate(row['arguments_correct'], row['arguments_known'])} |")

    lines.extend(["", "## GLM 的 Markdown 格式问题", ""])
    glm = summary["models"].get("glm")
    if glm is None:
        lines.append("本次没有 GLM 记录。")
    else:
        lines.extend([
            f"GLM 严格契约通过 {_rate(glm['contract_pass'], glm['total'])}，"
            f"其中 {glm['markdown_fence']} 次输出被 Markdown 代码块包裹，记为格式失败。"
            f"剥离代码块后，{glm['markdown_recovered_pass']} 次题目的工具和参数均正确；"
            "这部分只作为格式层诊断，不计入严格通过率。",
            "",
            "| 模型 | Markdown 代码块 | 剥离后可判定工具/参数 | 剥离后整题正确 |",
            "| --- | ---: | ---: | ---: |",
        ])
        for spec in record.get("models", []):
            item = summary["models"][spec["key"]]
            lines.append(
                f"| {labels[spec['key']]} | {item['markdown_fence']} | "
                f"{item['markdown_fence']} | {item['markdown_recovered_pass']} |")
        fenced_cases = [
            entry for entry in record.get("results", [])
            if entry.get("model") == "glm"
            and (entry.get("score") or {}).get("format_kind")
            in {"markdown_fence", "markdown_fence_invalid"}
        ]
        if fenced_cases:
            lines.extend(["", "涉及题面与诊断："])
            seen = set()
            for entry in fenced_cases:
                marker = (entry["case_id"], entry["repeat_index"])
                if marker in seen:
                    continue
                seen.add(marker)
                recovered = (entry.get("score") or {}).get("recovered")
                verdict = "剥离后通过" if recovered and recovered.get("passed") else "剥离后仍不通过"
                lines.append(
                    f"- `{entry['case_id']}` 第 {entry['repeat_index'] + 1} 次：{verdict}。")
        lines.extend([
            "",
            "本次 GLM 使用 Chat Completions 默认文本模式，未设置 `response_format=json_object`，"
            "因此可以观察模型在只靠提示词约束时的格式行为。Markdown 包裹属于输出契约失败，"
            "不能算作工具或参数能力失败；若要消除该层差异，应另做接口模式对照并单独报告，"
            "不能把两种接口配置的结果混在同一张表中。",
        ])

    failures = [entry for entry in record.get("results", [])
                if entry.get("status") != "scored"
                or (entry.get("score") or {}).get("failure_type") != "passed"]
    lines.extend(["", "## 失败样本摘要", ""])
    if not failures:
        lines.append("本次没有失败样本。")
    else:
        lines.extend([
            "| 模型 | 题目 | 轮次 | 类型 | 原始输出摘要 |",
            "| --- | --- | ---: | --- | --- |",
        ])
        for entry in failures:
            score = entry.get("score") or {}
            kind = ("call_error" if entry.get("status") != "scored"
                    else score.get("failure_type", "format"))
            detail = entry.get("output") if entry.get("status") == "scored" else entry.get("error_type")
            lines.append(
                f"| {labels.get(entry['model'], entry['model'])} | {entry['case_id']} | "
                f"{entry['repeat_index'] + 1} | {kind} | {_escape_cell(detail)} |")
        lines.extend(["", "完整原始输出、异常类型和 token 用量保存在私有运行记录中。"])
    lines.extend([
        "",
        "## 限制",
        "",
        "- 题目全部为合成题，题面较短，不能代表真实业务的工具选择分布。",
        "- 每题仅重复两次，只能观察一致性，不能估计稳定的总体准确率或置信区间。",
        "- 参数正确性采用严格结构比较；Python 代码先比较 AST，再用安全子集解释器接受变量赋值、"
        "f-string 等等价写法，不执行模型生成的任意代码。",
        "- 只覆盖一个供应商的两个模型，模型轴包含适配器与接口差异，不能单独归因于模型能力。",
        "- 未执行真实工具调用；本报告只评价规划阶段的工具与参数选择。",
        "",
    ])
    return "\n".join(lines)
