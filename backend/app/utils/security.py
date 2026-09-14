"""安全工具：密码哈希 + JWT 签发/校验（迭代1：多用户隔离）

安全红线：
- 密码用 bcrypt 哈希存储，绝不明文落库
- JWT payload 只放 user_id（身份字段）+ 过期时间，不放敏感信息
"""
from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

from app.config import JWT_EXPIRE_HOURS, JWT_SECRET_KEY

# bcrypt 哈希上下文（deprecated="auto" 支持未来平滑升级算法）
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

JWT_ALGORITHM = "HS256"


def create_token(user_id: int) -> str:
    """签发 JWT"""
    payload = {
        "user_id": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> int:
    """校验 JWT 并返回 user_id，失败抛 jwt.PyJWTError（由调用方转成 401）"""
    payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    return int(payload["user_id"])
