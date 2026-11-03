import sqlite3

from merchant_agent.tools.sql.init_orders_db import create_orders_db


def test_four_column_csv_fills_new_columns_with_null(tmp_path):
    csv_path = tmp_path / "o.csv"
    csv_path.write_text("order_id,store_id,paid_fen,refunded_fen\n1,A,100,0\n", encoding="utf-8")
    db = tmp_path / "o.sqlite"
    create_orders_db(str(csv_path), str(db))
    with sqlite3.connect(db) as connection:
        row = connection.execute(
            "SELECT order_date, category, channel, paid_fen FROM orders"
        ).fetchone()
    assert row == (None, None, None, 100)


def test_seven_column_csv_keeps_dimensions(tmp_path):
    csv_path = tmp_path / "o.csv"
    csv_path.write_text(
        "order_id,store_id,order_date,category,channel,paid_fen,refunded_fen\n"
        "1,A,2026-10-01,饮品,外卖,100,0\n",
        encoding="utf-8",
    )
    db = tmp_path / "o.sqlite"
    create_orders_db(str(csv_path), str(db))
    with sqlite3.connect(db) as connection:
        row = connection.execute("SELECT order_date, category, channel FROM orders").fetchone()
    assert row == ("2026-10-01", "饮品", "外卖")
