import sqlite3
from pathlib import Path


def _read_only_connection(db_path: str) -> sqlite3.Connection:
    """以只读模式连接评测数据库，避免工具改写环境快照。"""
    uri = Path(db_path).resolve().as_uri() + "?mode=ro"
    return sqlite3.connect(uri, uri=True)


def get_store_net(db_path: str, store_id: str) -> int | None:
    """查询指定门店的净支付金额，单位为分；门店不存在时返回空值。"""
    connection = _read_only_connection(db_path)
    try:
        cursor = connection.execute(
            "SELECT SUM(paid_fen - refunded_fen) FROM orders WHERE store_id = ?",
            (store_id,),
        )
        row = cursor.fetchone()
        return row[0] if row is not None else None
    finally:
        connection.close()


def get_store_order_count(db_path: str, store_id: str) -> int | None:
    """查询指定门店的订单数；门店不存在时返回空值，存在但无订单时返回 0。"""
    connection = _read_only_connection(db_path)
    try:
        exists = connection.execute(
            "SELECT 1 FROM orders WHERE store_id = ? LIMIT 1", (store_id,)
        ).fetchone()
        if exists is None:
            return None
        row = connection.execute(
            "SELECT COUNT(*) FROM orders WHERE store_id = ?", (store_id,)
        ).fetchone()
        return row[0] if row is not None else None
    finally:
        connection.close()


def get_store_refund_rate(db_path: str, store_id: str) -> float | None:
    """查询指定门店的退款率（已退款金额 / 已支付金额，0 到 1 的小数）。

    门店不存在时返回空值；支付金额为 0 时返回 0.0。结果四舍五入到 6 位小数。
    """
    connection = _read_only_connection(db_path)
    try:
        row = connection.execute(
            "SELECT SUM(paid_fen), SUM(refunded_fen) FROM orders WHERE store_id = ?",
            (store_id,),
        ).fetchone()
        paid, refunded = row if row is not None else (None, None)
        if paid is None:
            return None
        if paid == 0:
            return 0.0
        return round((refunded or 0) / paid, 6)
    finally:
        connection.close()


def get_store_aov(db_path: str, store_id: str) -> int | None:
    """查询指定门店的客单价（已支付金额 / 订单数），单位为分，向下取整。

    门店不存在或无订单时返回空值；口径为“平均每单已支付金额”，与净收入口径不同。
    """
    connection = _read_only_connection(db_path)
    try:
        row = connection.execute(
            "SELECT SUM(paid_fen), COUNT(*) FROM orders WHERE store_id = ?",
            (store_id,),
        ).fetchone()
        paid, count = row if row is not None else (None, 0)
        if paid is None or not count:
            return None
        return paid // count
    finally:
        connection.close()


def get_store_paid_total(db_path: str, store_id: str) -> int | None:
    """查询指定门店的已支付总额，单位为分；门店不存在时返回空值。"""
    connection = _read_only_connection(db_path)
    try:
        row = connection.execute(
            "SELECT SUM(paid_fen) FROM orders WHERE store_id = ?", (store_id,)
        ).fetchone()
        return row[0] if row is not None else None
    finally:
        connection.close()


def get_store_refunded_total(db_path: str, store_id: str) -> int | None:
    """查询指定门店的已退款总额，单位为分；门店不存在时返回空值。"""
    connection = _read_only_connection(db_path)
    try:
        row = connection.execute(
            "SELECT SUM(refunded_fen) FROM orders WHERE store_id = ?", (store_id,)
        ).fetchone()
        return row[0] if row is not None else None
    finally:
        connection.close()


def get_store_refunded_order_count(db_path: str, store_id: str) -> int | None:
    """查询指定门店发生过退款的订单数；门店不存在时返回空值，无退款订单时返回 0。"""
    connection = _read_only_connection(db_path)
    try:
        exists = connection.execute(
            "SELECT 1 FROM orders WHERE store_id = ? LIMIT 1", (store_id,)
        ).fetchone()
        if exists is None:
            return None
        row = connection.execute(
            "SELECT COUNT(*) FROM orders WHERE store_id = ? AND refunded_fen > 0",
            (store_id,),
        ).fetchone()
        return row[0] if row is not None else None
    finally:
        connection.close()
