import sqlite3

from merchant_agent.tools.sql.sql_query import (
    get_store_aov,
    get_store_net,
    get_store_order_count,
    get_store_paid_total,
    get_store_refund_rate,
    get_store_refunded_order_count,
    get_store_refunded_total,
)


def _db(tmp_path):
    db = tmp_path / "orders.sqlite"
    with sqlite3.connect(db) as connection:
        connection.execute(
            "CREATE TABLE orders (order_id TEXT, store_id TEXT, paid_fen INTEGER, refunded_fen INTEGER)"
        )
        connection.executemany("INSERT INTO orders VALUES (?, ?, ?, ?)", [
            ("1", "A", 10000, 2000),
            ("2", "A", 5000, 1000),
            ("3", "B", 8000, 0),
        ])
    return str(db)


def test_order_count_counts_rows_and_reports_missing_store(tmp_path):
    db = _db(tmp_path)
    assert get_store_order_count(db, "A") == 2
    assert get_store_order_count(db, "B") == 1
    assert get_store_order_count(db, "unknown") is None


def test_refund_rate_is_fraction_of_paid(tmp_path):
    db = _db(tmp_path)
    # A: 退款 3000 / 支付 15000 = 0.2；B 无退款应为 0.0。
    assert get_store_refund_rate(db, "A") == 0.2
    assert get_store_refund_rate(db, "B") == 0.0
    assert get_store_refund_rate(db, "unknown") is None


def test_aov_uses_paid_total_floor_division(tmp_path):
    db = _db(tmp_path)
    # A: 支付 15000 / 2 单 = 7500 分；B: 8000 / 1 = 8000 分。
    assert get_store_aov(db, "A") == 7500
    assert get_store_aov(db, "B") == 8000
    assert get_store_aov(db, "unknown") is None


def test_net_income_stays_unchanged(tmp_path):
    db = _db(tmp_path)
    assert get_store_net(db, "A") == 12000
    assert get_store_net(db, "unknown") is None


def test_paid_total_sums_paid_fen(tmp_path):
    db = _db(tmp_path)
    assert get_store_paid_total(db, "A") == 15000
    assert get_store_paid_total(db, "B") == 8000
    assert get_store_paid_total(db, "unknown") is None


def test_refunded_total_sums_refunded_fen(tmp_path):
    db = _db(tmp_path)
    assert get_store_refunded_total(db, "A") == 3000
    assert get_store_refunded_total(db, "B") == 0
    assert get_store_refunded_total(db, "unknown") is None


def test_refunded_order_count_only_counts_refunded_orders(tmp_path):
    db = _db(tmp_path)
    assert get_store_refunded_order_count(db, "A") == 2
    assert get_store_refunded_order_count(db, "B") == 0
    assert get_store_refunded_order_count(db, "unknown") is None
