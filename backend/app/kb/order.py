"""订单 + 维修记录查询（结构化精确查询）"""
from app.db.database import engine
from app.utils.logger import get_logger

logger = get_logger("query_order")


def query_order(order_no: str) -> str:
    """查询订单及其维修记录，返回格式化的文本供 Agent 判断。"""
    sql_order = """
        SELECT o.order_no, p.name, o.amount, o.created_at, o.status
        FROM orders o JOIN products p ON o.product_id = p.id
        WHERE o.order_no = %s
    """
    sql_repairs = """
        SELECT r.repair_date, r.fault, r.status
        FROM repairs r JOIN orders o ON r.order_id = o.id
        WHERE o.order_no = %s
        ORDER BY r.repair_date
    """
    try:
        with engine.raw_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql_order, (order_no,))
                order = cur.fetchone()
                cur.execute(sql_repairs, (order_no,))
                repairs = cur.fetchall()

        if not order:
            logger.warning("订单不存在", extra={"order_no": order_no})
            return f"订单 {order_no} 不存在"

        lines = [f"订单号：{order[0]}", f"商品：{order[1]}", f"金额：{order[2]}",
                 f"下单时间：{order[3]}", f"状态：{order[4]}"]
        if repairs:
            lines.append("维修记录：")
            for r in repairs:
                lines.append(f"  - {r[0]} {r[1]}（{r[2]}）")
        else:
            lines.append("维修记录：无")

        logger.info("订单查询", extra={"order_no": order_no, "repair_count": len(repairs)})
        return "\n".join(lines)
    except Exception as e:
        logger.error("订单查询失败", extra={"error": type(e).__name__}, exc_info=True)
        return f"[订单查询失败：{type(e).__name__}]"
