import csv
import sqlite3
from pathlib import Path

def create_orders_db(csv_path: str, db_path: str) -> None:
    """
    函数读取上一课的 CSV，
    在一个新的 SQLite 数据库中创建 orders 表并导入订单。
    表的四列与 CSV 同名：前两列用 TEXT，金额用 INTEGER，`order_id` 为主键。
    :param csv_path: CSV 文件路径
    :param db_path: SQLite 数据库路径
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
                paid_fen INTEGER,
                refunded_fen INTEGER
            )
            """
        )
        with open(csv_path, "r", encoding="utf-8",newline="") as file:
            reader = csv.DictReader(file)
            for row in reader:
                connection.execute(
                    "INSERT INTO orders VALUES (?, ?, ?, ?)",
                    (
                        row["order_id"],
                        row["store_id"],
                        int(row["paid_fen"]),
                        int(row["refunded_fen"]),
                    ),
                )
        connection.commit()
    finally:
        connection.close()
