"""只读 NL2SQL 工具：安全分层拒绝 + 结果集返回。"""

import re
import sqlite3
from pathlib import Path


MAX_QUERY_LENGTH = 2000
ROW_CAP = 100

_WRITE_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE|TRUNCATE|ATTACH|DETACH|PRAGMA|VACUUM)\b",
    re.IGNORECASE,
)


def run_sql(db_path: str, query: str) -> dict:
    """执行只读 SQL 并返回结构化结果集。

    拒绝分层：写/DDL/系统表 -> security_rejected（安全违规，hard fail）；
    多语句/超长/非查询 -> invalid_input（普通失败，可重试）。
    成功返回 columns/rows/row_count/truncated；超过 100 行截断并标记。
    """
    if not isinstance(query, str) or not query.strip():
        return {"outcome": "invalid_input", "message": "查询不能为空"}
    if len(query) > MAX_QUERY_LENGTH:
        return {"outcome": "invalid_input", "message": "查询过长"}
    stripped = query.strip()
    if _WRITE_KEYWORDS.search(stripped):
        return {"outcome": "security_rejected", "message": "禁止写操作或 DDL"}
    if "sqlite_" in stripped.lower():
        return {"outcome": "security_rejected", "message": "禁止访问系统表"}
    if not stripped.upper().startswith(("SELECT", "WITH")):
        return {"outcome": "invalid_input", "message": "只允许 SELECT/WITH 查询"}
    if ";" in stripped:
        return {"outcome": "invalid_input", "message": "禁止多语句"}
    try:
        uri = Path(db_path).resolve().as_uri() + "?mode=ro"
        connection = sqlite3.connect(uri, uri=True)
        try:
            cursor = connection.execute(stripped)
            columns = [description[0] for description in (cursor.description or [])]
            rows = [list(row) for row in cursor.fetchmany(ROW_CAP + 1)]
        finally:
            connection.close()
    except sqlite3.Error as exc:
        return {"outcome": "program_error", "message": str(exc)}
    truncated = len(rows) > ROW_CAP
    if truncated:
        rows = rows[:ROW_CAP]
    return {
        "outcome": "success",
        "columns": columns,
        "rows": rows,
        "row_count": len(rows),
        "truncated": truncated,
    }
