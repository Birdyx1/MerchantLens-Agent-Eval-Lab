"""只读 NL2SQL 工具：安全分层拒绝 + 结果集返回。"""

import sqlite3
from pathlib import Path


MAX_QUERY_LENGTH = 2000
ROW_CAP = 100

# 只有语句前缀是这些写/DDL 关键词时才判安全违规；
# 避免 SELECT 中的 replace() 等只读函数被全文正则误判。
_WRITE_STATEMENTS = frozenset({
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE",
    "REPLACE", "TRUNCATE", "ATTACH", "DETACH", "VACUUM",
})


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
    # 按语句前缀分类，避免 SELECT 里的 replace() 等只读函数被误判为写操作。
    first = stripped.split(None, 1)[0].upper() if stripped else ""
    if first in _WRITE_STATEMENTS:
        return {"outcome": "security_rejected", "message": "禁止写操作或 DDL"}
    if "sqlite_" in stripped.lower():
        return {"outcome": "security_rejected", "message": "禁止访问系统表"}
    if first not in {"SELECT", "WITH", "PRAGMA"}:
        return {"outcome": "invalid_input", "message": "只允许 SELECT/WITH/只读 PRAGMA 查询"}
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
