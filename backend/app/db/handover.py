"""接管单读写（转人工坐席接管的数据枢纽，迭代4）

状态机：pending(待接管) → active(接管中) → closed(已结束) / returned(已转回AI)
"""
import json

from psycopg.rows import dict_row

from app.db.database import engine
from app.utils.logger import get_logger

logger = get_logger("handover_db")

# 未完结状态（用户消息该走人工通道还是 AI 图，就看有没有未完结接管单）
OPEN_STATUSES = ("pending", "active")


def create_handover(
    thread_id: str, user_id: int | None, reason: str, user_request: str, agent_context: dict
) -> int:
    """写接管单，返回 handover_id"""
    sql = """
        INSERT INTO handovers (thread_id, user_id, reason, user_request, agent_context, status)
        VALUES (%s, %s, %s, %s, %s, 'pending')
        RETURNING id
    """
    with engine.raw_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (thread_id, user_id, reason, user_request,
                 json.dumps(agent_context, ensure_ascii=False)),
            )
            handover_id = cur.fetchone()[0]
        conn.commit()  # ⚠️ raw_connection 不会自动 commit
    logger.info("接管单已创建", extra={"handover_id": handover_id, "reason": reason})
    return handover_id


def get_open_handover_by_thread(thread_id: str) -> dict | None:
    """查会话的未完结接管单（pending/active）——chat 接口据此判断是否走人工通道"""
    sql = (
        "SELECT * FROM handovers WHERE thread_id = %s AND status IN ('pending','active') "
        "ORDER BY id DESC LIMIT 1"
    )
    with engine.raw_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, (thread_id,))
            return cur.fetchone()


def list_handovers(status: str | None = None) -> list[dict]:
    """接管单列表（管理端。pending 按等待时间正序——排队先来的先接）"""
    sql = """
        SELECT h.*, u.username
        FROM handovers h LEFT JOIN users u ON h.user_id = u.id
    """
    params: list = []
    if status:
        sql += " WHERE h.status = %s"
        params.append(status)
    sql += " ORDER BY CASE WHEN h.status = 'pending' THEN 0 ELSE 1 END, h.created_at ASC"
    with engine.raw_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, params)
            return cur.fetchall()


def get_handover(handover_id: int) -> dict | None:
    sql = """
        SELECT h.*, u.username
        FROM handovers h LEFT JOIN users u ON h.user_id = u.id
        WHERE h.id = %s
    """
    with engine.raw_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, (handover_id,))
            return cur.fetchone()


def take_handover(handover_id: int) -> bool:
    """接管（pending → active）。WHERE 带状态条件防并发重复接管"""
    sql = "UPDATE handovers SET status = 'active', taken_at = now() WHERE id = %s AND status = 'pending'"
    with engine.raw_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (handover_id,))
            ok = cur.rowcount > 0
        conn.commit()
    if ok:
        logger.info("坐席接管", extra={"handover_id": handover_id})
    return ok


def close_handover(handover_id: int, returned: bool = False) -> bool:
    """结束（active → closed）或转回 AI（active → returned）"""
    new_status = "returned" if returned else "closed"
    sql = f"UPDATE handovers SET status = %s, closed_at = now() WHERE id = %s AND status = 'active'"
    with engine.raw_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (new_status, handover_id))
            ok = cur.rowcount > 0
        conn.commit()
    if ok:
        logger.info("接管单完结", extra={"handover_id": handover_id, "status": new_status})
    return ok
