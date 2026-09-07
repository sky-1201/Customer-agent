"""知识库检索：FAQ / 故障说明语义检索（pgvector）"""
from app.db.database import engine
from app.kb import wrap_untrusted
from app.kb.embedding import embed
from app.utils.logger import get_logger

logger = get_logger("kb_search")


def _vec_str(vec: list[float]) -> str:
    """向量转 pgvector 字符串格式 [a,b,c,...]"""
    return "[" + ",".join(f"{v:.8f}" for v in vec) + "]"


def search_faq(query: str, top_k: int = 3) -> str:
    """语义检索 FAQ 库，返回最相关的问答对"""
    try:
        query_vec = embed(query)
    except Exception as e:
        logger.error("FAQ embedding 失败", extra={"error": type(e).__name__}, exc_info=True)
        return "[FAQ 检索失败：embedding 服务不可用]"

    sql = """
        SELECT question, answer
        FROM faqs
        ORDER BY question_embedding <=> %s::vector
        LIMIT %s
    """
    try:
        with engine.raw_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (_vec_str(query_vec), top_k))
                rows = cur.fetchall()
        logger.info("FAQ 检索完成", extra={"query": query[:20], "rows": len(rows)})
    except Exception as e:
        logger.error("FAQ 检索失败", extra={"error": type(e).__name__}, exc_info=True)
        return f"[FAQ 检索失败：{type(e).__name__}]"

    if not rows:
        return "未找到相关 FAQ。"

    parts = []
    for question, answer in rows:
        parts.append(f"【问题】{question}\n【答案】{answer}")
    return wrap_untrusted("\n\n".join(parts), "FAQ知识库")


def search_troubleshooting(query: str, top_k: int = 3) -> str:
    """语义检索故障说明库，返回最相关的故障知识（原因 + 排查方法）"""
    try:
        query_vec = embed(query)
    except Exception as e:
        logger.error("故障 embedding 失败", extra={"error": type(e).__name__}, exc_info=True)
        return "[故障检索失败：embedding 服务不可用]"

    sql = """
        SELECT fault, cause, solution
        FROM troubleshooting
        ORDER BY fault_embedding <=> %s::vector
        LIMIT %s
    """
    try:
        with engine.raw_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (_vec_str(query_vec), top_k))
                rows = cur.fetchall()
        logger.info("故障检索完成", extra={"query": query[:20], "rows": len(rows)})
    except Exception as e:
        logger.error("故障检索失败", extra={"error": type(e).__name__}, exc_info=True)
        return f"[故障检索失败：{type(e).__name__}]"

    if not rows:
        return "未找到相关故障说明。"

    parts = []
    for fault, cause, solution in rows:
        parts.append(f"【故障】{fault}\n【原因】{cause}\n【解决】{solution}")
    return wrap_untrusted("\n\n".join(parts), "故障知识库")
