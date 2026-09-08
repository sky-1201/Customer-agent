"""商品与订单查询（结构化数据，客户端数据底座）"""
from datetime import datetime

from psycopg.rows import dict_row

from app.db.database import engine
from app.utils.logger import get_logger

logger = get_logger("catalog_db")


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


def create_order(product_id: int) -> dict:
    """下单：生成订单号，插入订单，返回订单信息"""
    product = get_product(product_id)
    if product is None:
        raise ValueError(f"商品不存在: {product_id}")

    order_no = f"O-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    sql = """
        INSERT INTO orders (order_no, product_id, amount, status)
        VALUES (%s, %s, %s, '已完成')
        RETURNING id
    """
    with engine.raw_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (order_no, product_id, product["price"]))
            order_id = cur.fetchone()[0]
        conn.commit()  # ⚠️ raw_connection 不会自动 commit

    logger.info("下单成功", extra={"order_no": order_no, "product_id": product_id})
    return {"id": order_id, "order_no": order_no}


def delete_order(order_id: int) -> bool:
    """删除订单（先删其维修记录，再删订单，避免外键约束）"""
    sql_repairs = "DELETE FROM repairs WHERE order_id = %s"
    sql_order = "DELETE FROM orders WHERE id = %s"
    with engine.raw_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql_repairs, (order_id,))
            cur.execute(sql_order, (order_id,))
            deleted = cur.rowcount
        conn.commit()  # ⚠️ raw_connection 不会自动 commit
    logger.info("订单删除", extra={"order_id": order_id, "deleted": deleted})
    return deleted > 0


def list_orders() -> list[dict]:
    """订单列表（含商品名）"""
    sql = """
        SELECT o.id, o.order_no, o.amount, o.created_at, o.status,
               p.name AS product_name
        FROM orders o JOIN products p ON o.product_id = p.id
        ORDER BY o.id DESC
    """
    with engine.raw_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql)
            return cur.fetchall()


def get_order(order_id: int) -> dict | None:
    """订单详情（含维修记录）"""
    sql_order = """
        SELECT o.id, o.order_no, o.amount, o.created_at, o.status,
               p.name AS product_name, p.cpu, p.memory, p.storage, p.gpu, p.screen
        FROM orders o JOIN products p ON o.product_id = p.id
        WHERE o.id = %s
    """
    sql_repairs = """
        SELECT r.repair_date, r.fault, r.status
        FROM repairs r
        WHERE r.order_id = %s
        ORDER BY r.repair_date
    """
    with engine.raw_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql_order, (order_id,))
            order = cur.fetchone()
            if order is None:
                return None
            cur.execute(sql_repairs, (order_id,))
            order["repairs"] = cur.fetchall()
    return order
