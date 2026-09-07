"""审批单读写（HITL 数据枢纽，管理端"待审批详情页"读这张表）"""
import json

from psycopg.rows import dict_row

from app.db.database import engine
from app.utils.logger import get_logger

logger = get_logger("approval_db")


def create_approval(state: dict, decision) -> int:
    """写审批单，返回 approval_id"""
    thread_id = state.get("thread_id", "")
    user_request = state["messages"][-1].content
    tech = state.get("tech_result")
    aftersale = state.get("aftersale_result")

    tech_json = json.dumps(tech.model_dump(), ensure_ascii=False) if tech else None
    aftersale_json = json.dumps(aftersale.model_dump(), ensure_ascii=False) if aftersale else None

    sql = """
        INSERT INTO approvals
            (thread_id, user_request, tech_result, aftersale_result,
             decision, policy_ref, comfort_msg, confidence, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pending')
        RETURNING id
    """
    with engine.raw_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    thread_id, user_request, tech_json, aftersale_json,
                    decision.conclusion, decision.policy_ref,
                    decision.comfort_msg, decision.confidence,
                ),
            )
            approval_id = cur.fetchone()[0]
        conn.commit()  # ⚠️ raw_connection 不会自动 commit，必须显式提交

    logger.info("审批单已创建", extra={"approval_id": approval_id, "conclusion": decision.conclusion})
    return approval_id


def list_approvals() -> list[dict]:
    """待审批列表（管理端展示）"""
    sql = """
        SELECT id, user_request, decision, confidence, status
        FROM approvals
        WHERE status = 'pending'
        ORDER BY id DESC
    """
    with engine.raw_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql)
            return cur.fetchall()


def get_approval_by_thread(thread_id: str) -> dict | None:
    """按 thread_id 查审批单（客户端轮询审批结果用）"""
    sql = "SELECT * FROM approvals WHERE thread_id = %s ORDER BY id DESC LIMIT 1"
    with engine.raw_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, (thread_id,))
            return cur.fetchone()


def get_approval(approval_id: int) -> dict | None:
    """审批详情（含 thread_id，供 resume 用）"""
    sql = "SELECT * FROM approvals WHERE id = %s"
    with engine.raw_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, (approval_id,))
            return cur.fetchone()


def update_approval(approval_id: int, status: str) -> None:
    """更新审批单状态（pending → approved/rejected）"""
    sql = "UPDATE approvals SET status = %s WHERE id = %s"
    with engine.raw_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (status, approval_id))
        conn.commit()  # ⚠️ raw_connection 不会自动 commit，必须显式提交
    logger.info("审批单状态更新", extra={"approval_id": approval_id, "status": status})
