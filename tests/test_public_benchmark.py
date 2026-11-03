"""防止答案泄漏、只读越权、截断误评分和重复试验统计偏差。"""

import asyncio
import json
import sqlite3
from pathlib import Path

import pytest

from merchant_agent.agent.model_port import ModelResponse
from merchant_agent.evaluation import public_benchmark as bench
from merchant_agent.evaluation import public_benchmark_cli as cli
from merchant_agent.evaluation.benchmark_data import MANIFEST, verify_manifest


@pytest.fixture
def database(tmp_path):
    path = tmp_path / "test.sqlite"
    with sqlite3.connect(path) as connection:
        connection.executescript("CREATE TABLE orders(id INTEGER, amount INTEGER); INSERT INTO orders VALUES(1,10),(2,20);")
    return path


@pytest.mark.parametrize("sql", ["DELETE FROM orders", "DROP TABLE orders", "PRAGMA user_version=1",
                                 "ATTACH DATABASE ':memory:' AS x", "SELECT load_extension('x')",
                                 "WITH x AS (SELECT 1) DELETE FROM orders"])
def test_model_sql_cannot_write_or_escape(database, sql):
    with pytest.raises(sqlite3.Error):
        bench.run_readonly_sql(database, sql)
    assert bench.run_readonly_sql(database, "SELECT SUM(amount) FROM orders")["rows"] == [(30,)]


def test_complete_scoring_rows_cannot_be_silently_truncated(database):
    with pytest.raises(ValueError, match="不能截断"):
        bench.run_readonly_sql(database, "SELECT * FROM orders", row_limit=1)


def test_slow_query_is_interrupted(database):
    with pytest.raises(sqlite3.OperationalError, match="interrupted"):
        bench.run_readonly_sql(database, "WITH RECURSIVE n(x) AS (VALUES(1) UNION ALL SELECT x+1 FROM n) SELECT SUM(x) FROM n", timeout=.01)


def test_schema_and_evidence_visible_but_oracle_hidden(monkeypatch):
    monkeypatch.setattr(bench, "schema_for", lambda _: "CREATE TABLE t(x INTEGER)")
    case = {"db_id": "test", "input": {"question": "count", "evidence": "public fact"}, "oracle": "SECRET_REFERENCE_SQL"}
    for arm in ("direct", "react"):
        text = json.dumps(bench.bird_messages(case, arm))
        assert "public fact" in text and "CREATE TABLE" in text
        assert "SECRET_REFERENCE_SQL" not in text
    case = {"input": {"question": [[{"role": "user", "content": "help"}]], "function": []}, "oracle": "SECRET_REFERENCE_CALL"}
    assert "SECRET_REFERENCE_CALL" not in json.dumps(bench.bfcl_messages(case))


def test_empty_call_and_format_are_separate_failures():
    case = {"category": "irrelevance"}
    assert bench.score_bfcl(case, "[]", None)["passed"]
    assert bench.score_bfcl(case, '[{"name":"x","arguments":{}}]', None)["failure_type"] == "unnecessary_tool_call"
    assert bench.score_bfcl(case, "```json\n[]\n```", None)["failure_type"] == "format_error"


def test_react_can_recover_from_query_error_without_seeing_gold(database, tmp_path, monkeypatch):
    monkeypatch.setattr(bench, "schema_for", lambda _: "CREATE TABLE orders(id INTEGER, amount INTEGER)")
    monkeypatch.setattr(cli, "database_path", lambda _: database)
    outputs = ['{"action":"query","sql":"SELECT missing FROM orders"}',
               '{"action":"query","sql":"SELECT SUM(amount) FROM orders"}',
               '{"action":"finish","sql":"SELECT SUM(amount) FROM orders"}']

    class Model:
        async def generate(self, messages):
            assert "SECRET_ORACLE" not in json.dumps(messages)
            return ModelResponse(outputs.pop(0), "fake", 10, 5)

    case = {"benchmark": "bird", "id": "t", "db_id": "db", "difficulty": "simple",
            "input": {"question": "total", "evidence": ""}, "oracle": "SECRET_ORACLE"}
    slot = {"index": 0, "benchmark": "bird", "case_id": "t", "model": "fake", "arm": "react", "repeat": 0}
    result = asyncio.run(cli.run_attempt(slot, case, Model(), {"rows": [(30,)]},
                                        lambda a, b: int(set(a) == set(b)), tmp_path))
    assert result["passed"] and result["tool_calls"] == 2 and result["model_calls"] == 3
    assert result["trace"][1]["observation"]["error_type"] == "OperationalError"
    assert result["input_tokens"] == 30


def test_statistics_keep_failed_trials_and_require_complete_repeats():
    base = {"benchmark": "bfcl", "model": "m", "arm": "a", "category": "simple",
            "elapsed_seconds": 1, "input_tokens": 0, "output_tokens": 0,
            "tool_calls": 0, "model_calls": 1}
    rows = [{**base, "case_id": "t", "repeat": i, "passed": i == 0,
             "status": "scored" if i == 0 else "error", "failure_type": None if i == 0 else "api_error"}
            for i in range(3)]
    summary = cli.summarize(rows, 3)[0]
    assert summary["success_rate"] == 1 / 3
    assert summary["all_repeats_success_rate"] == 0
    assert summary["at_least_one_success_rate"] == 1
    assert summary["token_observed_trials"] == 1
    assert cli.summarize(rows[:2], 3)[0]["all_repeats_success_rate"] is None


def test_manifest_schedule_covers_every_cell_and_repeat():
    manifest = json.loads(MANIFEST.read_text())
    schedule = cli.build_schedule(manifest)
    assert len(schedule) == 240
    assert schedule == cli.build_schedule(manifest)
    assert len({(s["case_id"], s["model"], s["arm"], s["repeat"]) for s in schedule}) == 240
    assert {s["repeat"] for s in schedule} == {0, 1, 2}


def test_audit_rejects_dropped_duplicated_or_reassigned_trials():
    from merchant_agent.evaluation.benchmark_audit import validate_rows
    schedule = [{"index": i, "case_id": f"t{i}", "repeat": 0} for i in range(2)]
    rows = [{**slot, "passed": False, "status": "scored"} for slot in schedule]
    validate_rows(schedule, rows)
    with pytest.raises(ValueError, match="重复或缺失"):
        validate_rows(schedule, rows[:1])
    with pytest.raises(ValueError, match="重复或缺失"):
        validate_rows(schedule, [rows[0], rows[0]])
    with pytest.raises(ValueError, match="调度不一致"):
        validate_rows(schedule, [rows[0], {**rows[1], "case_id": "t0"}])
    with pytest.raises(ValueError, match="不能计为通过"):
        validate_rows(schedule, [rows[0], {**rows[1], "status": "error", "passed": True}])


def test_hash_mismatch_blocks_execution(tmp_path, monkeypatch):
    from merchant_agent.evaluation import benchmark_data
    monkeypatch.setattr(benchmark_data, "CACHE", tmp_path)
    monkeypatch.setattr(benchmark_data, "ROOT", tmp_path)
    path = tmp_path / "source.json"
    path.write_text("changed")
    with pytest.raises(ValueError, match="哈希变化"):
        verify_manifest({"sources": [{"path": "source.json", "sha256": "0" * 64}]})


@pytest.mark.skipif(not (bench.CACHE / "bird/evaluation/evaluation_ex.py").exists(), reason="需先 restore 官方评分器")
def test_official_bird_ex_is_order_insensitive_set_comparison():
    check = bench.bird_checker()
    assert check([(1,), (2,)], [(2,), (1,)]) == 1
    assert check([(1,), (1,)], [(1,)]) == 1
    assert check([(1.000001,)], [(1.0,)]) == 0


@pytest.mark.skipif(not (bench.CACHE / "bfcl" / f"{bench.BFCL_PREFIX}eval_checker/ast_eval/ast_checker.py").exists(), reason="需先 restore 官方评分器")
def test_official_bfcl_checker_accepts_reference_calls_and_rejects_wrong_function():
    checker = bench.bfcl_checker()
    manifest = json.loads(MANIFEST.read_text())
    for case in manifest["cases"]:
        if case["benchmark"] != "bfcl" or case["category"] == "irrelevance":
            continue
        calls = [{"name": name, "arguments": {key: values[0] for key, values in args.items() if values[0] != ""}}
                 for answer in case["oracle"] for name, args in answer.items()]
        assert bench.score_bfcl(case, json.dumps(calls), checker)["passed"], case["id"]
        calls[0]["name"] = "wrong_function"
        assert not bench.score_bfcl(case, json.dumps(calls), checker)["passed"]
