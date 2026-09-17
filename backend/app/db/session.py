"""会话表读写（迭代5：会话管理——历史会话列表 / 多会话 / 归档）

会话与消息的关系：消息在 LangGraph checkpoint（事实源），sessions 表只是
"会话索引"（用户视角的会话列表），首条消息时自动建档。
"""
from psycopg.rows import dict_row

from app.db.database import engine
from app.utils.logger import get_logger

logger = get_logger("session_db")


def upsert_session(user_id: int, session_id: str, first_message: str) -> None:
    """会话建档/更新活跃时间。title 取首条用户消息截断（之后的消息不改标题）"""
    title = first_message.strip()[:30]
    sql = """
        INSERT INTO sessions (user_id, session_id, title)
        VALUES (%s, %s, %s)
        ON CONFLICT (user_id, session_id)
        DO UPDATE SET updated_at = now()
    """
    with engine.raw_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (user_id, session_id, title))
        conn.commit()


def list_sessions(user_id: int) -> list[dict]:
    """当前用户的会话列表（未归档，最近活跃在前）"""
    sql = """
        SELECT session_id, title, created_at, updated_at
        FROM sessions
        WHERE user_id = %s AND archived = FALSE
        ORDER BY updated_at DESC
    """
    with engine.raw_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, (user_id,))
            return cur.fetchall()


def archive_session(user_id: int, session_id: str) -> bool:
    """归档会话（安全红线：只能归档自己的）"""
    sql = "UPDATE sessions SET archived = TRUE WHERE user_id = %s AND session_id = %s"
    with engine.raw_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (user_id, session_id))
            ok = cur.rowcount > 0
        conn.commit()
    if ok:
        logger.info("会话归档", extra={"user_id": user_id, "session_id": session_id})
    return ok
