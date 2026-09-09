"""订单 + 维修记录查询（结构化精确查询）"""
from app.db.database import engine
from app.utils.logger import get_logger

logger = get_logger("query_order")


def query_order(order_no: str) -> dict | None:
    """查询订单及其维修记录，返回结构化 dict（订单号、购买时间、维修记录等）"""
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
                if order is None:
                    logger.warning("订单不存在", extra={"order_no": order_no})
                    return None
                cur.execute(sql_repairs, (order_no,))
                repairs = cur.fetchall()

        logger.info("订单查询", extra={"order_no": order_no, "repair_count": len(repairs)})
        return {
            "order_no": order[0],
            "product_name": order[1],
            "amount": order[2],
            "purchase_date": str(order[3]),  # 购买时间
            "status": order[4],
            "repairs": [
                {"repair_date": str(r[0]), "fault": r[1], "status": r[2]}
                for r in repairs
            ],
        }
    except Exception as e:
        logger.error("订单查询失败", extra={"error": type(e).__name__}, exc_info=True)
        return None


def format_order(order: dict) -> str:
    """格式化订单信息为文本（给 LLM 判断用）"""
    lines = [
        f"订单号：{order['order_no']}",
        f"商品：{order['product_name']}",
        f"金额：{order['amount']}",
        f"下单时间：{order['purchase_date']}",
        f"状态：{order['status']}",
    ]
    if order["repairs"]:
        lines.append("维修记录：")
        for r in order["repairs"]:
            lines.append(f"  - {r['repair_date']} {r['fault']}（{r['status']}）")
    else:
        lines.append("维修记录：无")
    return "\n".join(lines)
