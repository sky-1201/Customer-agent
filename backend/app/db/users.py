"""用户表读写（注册 / 登录校验）"""
import psycopg
from psycopg.rows import dict_row

from app.db.database import engine
from app.utils.logger import get_logger
from app.utils.security import pwd_context

logger = get_logger("users_db")


def create_user(username: str, password: str) -> int:
    """注册：存 bcrypt 哈希（绝不存明文），返回 user_id。用户名冲突抛 ValueError"""
    sql = "INSERT INTO users (username, password_hash) VALUES (%s, %s) RETURNING id"
    try:
        with engine.raw_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (username, pwd_context.hash(password)))
                user_id = cur.fetchone()[0]
            conn.commit()  # ⚠️ raw_connection 不会自动 commit
    except psycopg.errors.UniqueViolation:
        logger.warning("注册失败：用户名已存在", extra={"username": username})
        raise ValueError("用户名已存在")

    logger.info("用户注册", extra={"user_id": user_id, "username": username})
    return user_id


def get_user_by_username(username: str) -> dict | None:
    """按用户名查用户（含密码哈希，仅登录校验内部使用）"""
    sql = "SELECT id, username, password_hash FROM users WHERE username = %s"
    with engine.raw_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, (username,))
            return cur.fetchone()


def verify_user(username: str, password: str) -> int | None:
    """登录校验：成功返回 user_id，失败返回 None。

    失败不区分"用户不存在"和"密码错误"（防用户名枚举），也不记录密码。
    """
    user = get_user_by_username(username)
    if user is None or not pwd_context.verify(password, user["password_hash"]):
        return None
    return user["id"]
