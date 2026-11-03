import sqlite3

from merchant_agent.tools.sql.run_sql import run_sql


def _seed_db(tmp_path):
    db = tmp_path / "o.sqlite"
    with sqlite3.connect(db) as connection:
        connection.execute(
            "CREATE TABLE orders (order_id TEXT, store_id TEXT, paid_fen INTEGER, refunded_fen INTEGER)"
        )
        connection.executemany("INSERT INTO orders VALUES (?, ?, ?, ?)", [
            ("1", "A", 100, 0),
            ("2", "A", 200, 50),
            ("3", "B", 300, 100),
        ])
    return db


def _seed_big_db(tmp_path, n=150):
    db = tmp_path / "big.sqlite"
    with sqlite3.connect(db) as connection:
        connection.execute(
            "CREATE TABLE orders (order_id TEXT, store_id TEXT, paid_fen INTEGER, refunded_fen INTEGER)"
        )
        connection.executemany(
            "INSERT INTO orders VALUES (?, ?, ?, ?)",
            [(str(i), "A", 100, 0) for i in range(n)],
        )
    return db


def test_select_returns_result_set(tmp_path):
    db = _seed_db(tmp_path)
    result = run_sql(str(db), "SELECT COUNT(*) AS c FROM orders")
    assert result["outcome"] == "success"
    assert result["columns"] == ["c"]
    assert result["rows"] == [[3]]


def test_trailing_semicolon_is_invalid_not_security(tmp_path):
    db = _seed_db(tmp_path)
    result = run_sql(str(db), "SELECT COUNT(*) FROM orders;")
    assert result["outcome"] == "invalid_input"


def test_write_statement_is_security_rejected(tmp_path):
    db = _seed_db(tmp_path)
    result = run_sql(str(db), "DROP TABLE orders")
    assert result["outcome"] == "security_rejected"


def test_system_table_is_security_rejected(tmp_path):
    db = _seed_db(tmp_path)
    result = run_sql(str(db), "SELECT * FROM sqlite_master")
    assert result["outcome"] == "security_rejected"


def test_row_cap_truncates(tmp_path):
    db = _seed_big_db(tmp_path, n=150)
    result = run_sql(str(db), "SELECT * FROM orders")
    assert result["row_count"] == 100
    assert result["truncated"] is True


def test_select_replace_function_is_not_security(tmp_path):
    # replace() 是只读函数，不应因关键字出现在 SELECT 中就被判 security_rejected。
    db = _seed_db(tmp_path)
    result = run_sql(str(db), "SELECT replace(store_id, 'A', 'a') AS s FROM orders")
    assert result["outcome"] != "security_rejected"


def test_pragma_table_info_is_allowed(tmp_path):
    db = _seed_db(tmp_path)
    result = run_sql(str(db), "PRAGMA table_info(orders)")
    assert result["outcome"] != "security_rejected"
