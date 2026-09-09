"""政策查询（结构化精确查询，非向量检索）

三包政策是"结构化知识"，必须字段化精确查询，禁止用向量检索。
"""
from app.db.database import engine
from app.utils.logger import get_logger

logger = get_logger("query_policy")

# 政策字段映射（condition 用 enum 限定，防止 SQL 注入）
_FIELD_MAP = {
    "warranty_period": "warranty_period",          # 整机保修期
    "major_parts": "major_parts",                  # 主要部件清单
    "replace_condition": "replace_condition",      # 换货条件
    "return_condition": "return_condition",        # 退货条件
}


def query_policy(condition: str) -> str:
    """查询三包政策的指定条款，返回字段值。

    condition 取值：warranty_period / major_parts / replace_condition / return_condition
    """
    field = _FIELD_MAP.get(condition)
    if not field:
        logger.warning("未知政策项", extra={"condition": condition})
        return "未知政策项"

    sql = f"SELECT {field} FROM policies LIMIT 1"
    try:
        with engine.raw_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                row = cur.fetchone()
        if row and row[0]:
            logger.info("政策查询", extra={"condition": condition})
            return row[0]
        logger.warning("政策查询为空", extra={"condition": condition})
        return "未找到相关政策"
    except Exception as e:
        logger.error("政策查询失败", extra={"error": type(e).__name__}, exc_info=True)
        return f"[政策查询失败：{type(e).__name__}]"


def query_full_policy() -> str:
    """查询完整三包政策（所有字段组合，供审批展示完整依据）"""
    sql = """
        SELECT category, warranty_period, major_parts_period, major_parts,
               replace_condition, return_condition, source
        FROM policies LIMIT 1
    """
    try:
        with engine.raw_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                row = cur.fetchone()
        if not row:
            return "未找到政策"

        category, warranty, major_period, major_parts, replace, return_cond, source = row
        policy = (
            f"【{category}三包政策】\n"
            f"整机保修期：{warranty}\n"
            f"主要部件保修期：{major_period}\n"
            f"主要部件清单：{major_parts}\n"
            f"换货条件：{replace}\n"
            f"退货条件：{return_cond}\n"
            f"政策出处：{source}"
        )
        logger.info("完整政策查询")
        return policy
    except Exception as e:
        logger.error("完整政策查询失败", extra={"error": type(e).__name__}, exc_info=True)
        return f"[政策查询失败：{type(e).__name__}]"
