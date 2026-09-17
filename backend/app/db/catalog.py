"""商品与订单查询（结构化数据，客户端数据底座）"""
import random
from datetime import datetime

from psycopg.rows import dict_row

from app.db.database import engine
from app.utils.logger import get_logger

logger = get_logger("catalog_db")

# 订单状态机（迭代5）：合法流转表，禁止非法流转
ALLOWED_TRANSITIONS = {
    "已完成": {"退换货中"},
    "退换货中": {"已退换"},
    "已退换": set(),  # 终态
}


def transition_order_by_no(order_no: str, user_id: int, to_status: str, reason: str) -> bool:
    """订单状态流转（带状态机校验 + 流转日志，全程可追溯）

    只允许 ALLOWED_TRANSITIONS 里的流转（如 已完成→退换货中），
    非法流转拒绝并记 WARNING（如 已完成→已退换 跳步、终态再流转）。
    """
    sql_get = "SELECT id, status FROM orders WHERE order_no = %s AND user_id = %s"
    sql_update = "UPDATE orders SET status = %s WHERE id = %s"
    sql_log = """
        INSERT INTO order_events (order_id, from_status, to_status, reason)
        VALUES (%s, %s, %s, %s)
    """
    with engine.raw_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql_get, (order_no, user_id))
            row = cur.fetchone()
            if row is None:
                logger.warning("状态流转失败：订单不存在", extra={"order_no": order_no})
                return False
            order_id, from_status = row
            if to_status not in ALLOWED_TRANSITIONS.get(from_status, set()):
                logger.warning(
                    "非法订单流转被拒绝",
                    extra={"order_no": order_no, "from": from_status, "to": to_status},
                )
                return False
            cur.execute(sql_update, (to_status, order_id))
            cur.execute(sql_log, (order_id, from_status, to_status, reason))
        conn.commit()
    logger.info(
        "订单状态流转",
        extra={"order_no": order_no, "from": from_status, "to": to_status, "reason": reason},
    )
    return True


def list_products() -> list[dict]:
    """商品列表（21 个笔记本）"""
    sql = "SELECT * FROM products ORDER BY id"
    with engine.raw_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql)
            return cur.fetchall()


def get_product(product_id: int) -> dict | None:
    """商品详情"""
    sql = "SELECT * FROM products WHERE id = %s"
    with engine.raw_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, (product_id,))
            return cur.fetchone()


def create_order(product_id: int, user_id: int) -> dict:
    """下单：生成订单号，插入订单（归属当前用户），返回订单信息"""
    product = get_product(product_id)
    if product is None:
        raise ValueError(f"商品不存在: {product_id}")

    # 订单号：秒级时间戳 + 3 位随机数防撞单（迭代3），UNIQUE 约束兜底
    order_no = f"O-{datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(100, 999)}"
    sql = """
        INSERT INTO orders (order_no, product_id, user_id, amount, status)
        VALUES (%s, %s, %s, %s, '已完成')
        RETURNING id
    """
    with engine.raw_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (order_no, product_id, user_id, product["price"]))
            order_id = cur.fetchone()[0]
        conn.commit()  # ⚠️ raw_connection 不会自动 commit

    logger.info("下单成功", extra={"order_no": order_no, "product_id": product_id, "user_id": user_id})
    return {"id": order_id, "order_no": order_no}


def delete_order(order_id: int, user_id: int) -> bool:
    """删除订单（先删其维修记录，再删订单；只能删自己的，WHERE 双条件防越权）"""
    sql_repairs = """
        DELETE FROM repairs WHERE order_id IN (
            SELECT id FROM orders WHERE id = %s AND user_id = %s
        )
    """
    sql_order = "DELETE FROM orders WHERE id = %s AND user_id = %s"
    with engine.raw_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql_repairs, (order_id, user_id))
            cur.execute(sql_order, (order_id, user_id))
            deleted = cur.rowcount
        conn.commit()  # ⚠️ raw_connection 不会自动 commit
    logger.info("订单删除", extra={"order_id": order_id, "user_id": user_id, "deleted": deleted})
    return deleted > 0


def list_orders(user_id: int) -> list[dict]:
    """订单列表（安全红线：只查当前用户的）"""
    sql = """
        SELECT o.id, o.order_no, o.amount, o.created_at, o.status,
               p.name AS product_name
        FROM orders o JOIN products p ON o.product_id = p.id
        WHERE o.user_id = %s
        ORDER BY o.id DESC
    """
    with engine.raw_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, (user_id,))
            return cur.fetchall()


def get_order(order_id: int, user_id: int) -> dict | None:
    """订单详情（含维修记录）。越权访问返回 None（与不存在统一 404，不暴露订单是否存在）"""
    sql_order = """
        SELECT o.id, o.order_no, o.amount, o.created_at, o.status,
               p.name AS product_name, p.cpu, p.memory, p.storage, p.gpu, p.screen
        FROM orders o JOIN products p ON o.product_id = p.id
        WHERE o.id = %s AND o.user_id = %s
    """
    sql_repairs = """
        SELECT r.repair_date, r.fault, r.status
        FROM repairs r
        WHERE r.order_id = %s
        ORDER BY r.repair_date
    """
    sql_events = """
        SELECT from_status, to_status, reason, created_at
        FROM order_events
        WHERE order_id = %s
        ORDER BY id
    """
    with engine.raw_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql_order, (order_id, user_id))
            order = cur.fetchone()
            if order is None:
                return None
            cur.execute(sql_repairs, (order_id,))
            order["repairs"] = cur.fetchall()
            cur.execute(sql_events, (order_id,))
            order["events"] = cur.fetchall()  # 状态流转记录（迭代5）
    return order
