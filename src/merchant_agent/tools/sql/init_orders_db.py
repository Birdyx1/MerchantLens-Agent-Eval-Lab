import csv
import sqlite3
from pathlib import Path


# 门店维度数据是可选的：存在则建 stores 表，不存在（如单元测试的 tmp_path）则跳过。
STORES_CSV = Path(__file__).resolve().parents[4] / "fixtures" / "business_data" / "stores.csv"


def create_orders_db(csv_path: str, db_path: str) -> None:
    """
    读取订单 CSV，建 7 列 orders 表；若存在 stores.csv 则一并建门店维度表。

    旧 4 列 CSV 的 order_date / category / channel 写入 NULL，保持既有评测兼容；
    7 列 CSV（含维度）则原样导入。order_id 为主键，金额列用 INTEGER。
    :param csv_path: 订单 CSV 路径
    :param db_path: 目标 SQLite 数据库路径（必须不存在）
    :return: None
    """
    if Path(db_path).exists():
        raise FileExistsError(f"db_path: {db_path}")
    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            """
            CREATE TABLE orders (
                order_id TEXT PRIMARY KEY,
                store_id TEXT,
                order_date TEXT,
                category TEXT,
                channel TEXT,
                paid_fen INTEGER,
                refunded_fen INTEGER
            )
            """
        )
        with open(csv_path, "r", encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file)
            for row in reader:
                connection.execute(
                    "INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        row["order_id"],
                        row["store_id"],
                        row.get("order_date"),
                        row.get("category"),
                        row.get("channel"),
                        int(row["paid_fen"]),
                        int(row["refunded_fen"]),
                    ),
                )
        if STORES_CSV.is_file():
            connection.execute(
                """
                CREATE TABLE stores (
                    store_id TEXT PRIMARY KEY,
                    store_name TEXT,
                    region TEXT,
                    city TEXT
                )
                """
            )
            with open(STORES_CSV, "r", encoding="utf-8", newline="") as file:
                for row in csv.DictReader(file):
                    connection.execute(
                        "INSERT INTO stores VALUES (?, ?, ?, ?)",
                        (row["store_id"], row["store_name"], row["region"], row["city"]),
                    )
        connection.commit()
    finally:
        connection.close()
