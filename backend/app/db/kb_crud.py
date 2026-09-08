"""知识库管理（CRUD：FAQ / 故障说明 / 政策）"""
from psycopg.rows import dict_row

from app.db.database import engine
from app.kb.embedding import embed
from app.utils.logger import get_logger

logger = get_logger("kb_crud")

# 政策表允许更新的字段白名单（防 SQL 注入）
_POLICY_FIELDS = {
    "warranty_period", "major_parts_period", "major_parts",
    "replace_condition", "return_condition", "source",
}


def _vec_str(vec: list[float]) -> str:
    """向量转 pgvector 字符串格式"""
    return "[" + ",".join(f"{v:.8f}" for v in vec) + "]"


# ========== FAQ ==========

def list_faqs() -> list[dict]:
    sql = "SELECT id, question, answer FROM faqs ORDER BY id"
    with engine.raw_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql)
            return cur.fetchall()


def add_faq(question: str, answer: str) -> int:
    """新增 FAQ（生成 question 向量，供 RAG 召回）"""
    vec = embed(question)
    sql = (
        "INSERT INTO faqs (question, answer, question_embedding) "
        "VALUES (%s, %s, %s::vector) RETURNING id"
    )
    with engine.raw_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (question, answer, _vec_str(vec)))
            faq_id = cur.fetchone()[0]
        conn.commit()  # ⚠️ raw_connection 不会自动 commit
    logger.info("FAQ 新增", extra={"faq_id": faq_id})
    return faq_id


def delete_faq(faq_id: int) -> bool:
    sql = "DELETE FROM faqs WHERE id = %s"
    with engine.raw_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (faq_id,))
            deleted = cur.rowcount
        conn.commit()
    return deleted > 0


# ========== 故障说明 ==========

def list_troubleshooting() -> list[dict]:
    sql = "SELECT id, product_model, fault, cause, solution FROM troubleshooting ORDER BY id"
    with engine.raw_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql)
            return cur.fetchall()


def add_troubleshooting(product_model: str | None, fault: str, cause: str, solution: str) -> int:
    """新增故障说明（生成 fault 向量）"""
    vec = embed(fault)
    sql = (
        "INSERT INTO troubleshooting (product_model, fault, cause, solution, fault_embedding) "
        "VALUES (%s, %s, %s, %s, %s::vector) RETURNING id"
    )
    with engine.raw_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (product_model, fault, cause, solution, _vec_str(vec)))
            t_id = cur.fetchone()[0]
        conn.commit()
    logger.info("故障说明新增", extra={"id": t_id, "fault": fault})
    return t_id


def delete_troubleshooting(t_id: int) -> bool:
    sql = "DELETE FROM troubleshooting WHERE id = %s"
    with engine.raw_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (t_id,))
            deleted = cur.rowcount
        conn.commit()
    return deleted > 0


# ========== 政策 ==========

def list_policies() -> list[dict]:
    sql = "SELECT * FROM policies ORDER BY id"
    with engine.raw_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql)
            return cur.fetchall()


def update_policy(policy_id: int, fields: dict) -> bool:
    """更新政策字段（字段名走白名单，防 SQL 注入）"""
    updates = {k: v for k, v in fields.items() if k in _POLICY_FIELDS and v is not None}
    if not updates:
        return False
    set_clause = ", ".join(f"{k} = %s" for k in updates)
    sql = f"UPDATE policies SET {set_clause} WHERE id = %s"
    with engine.raw_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, [*updates.values(), policy_id])
        conn.commit()
    logger.info("政策更新", extra={"policy_id": policy_id, "fields": list(updates.keys())})
    return True
