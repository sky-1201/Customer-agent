"""认证接口（注册 / 登录）+ 鉴权依赖（迭代1：多用户隔离）

鉴权方案：JWT（标准、无状态）。
- 注册/登录成功即签发 token（注册免二次登录）
- 其余 C 端接口通过 get_current_user 依赖从 token 解析 user_id
"""
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from app.db import users as users_db
from app.utils.limiter import limiter
from app.utils.logger import get_logger
from app.utils.security import create_token, decode_token

router = APIRouter()
logger = get_logger(__name__)

# bcrypt 算法只处理密码前 72 字节，超长直接报错，注册/登录前先校验
MAX_PASSWORD_BYTES = 72


class AuthRequest(BaseModel):
    username: str = Field(min_length=2, max_length=50)
    password: str = Field(min_length=6, max_length=100)


@router.post("/auth/register")
@limiter.limit("20/minute")  # 迭代5：限流防批量注册
def register(request: Request, req: AuthRequest):
    """注册（成功即登录，直接返回 token）"""
    if len(req.password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise HTTPException(status_code=400, detail="密码过长（不超过 72 字节）")
    try:
        user_id = users_db.create_user(req.username, req.password)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {"token": create_token(user_id), "username": req.username}


@router.post("/auth/login")
@limiter.limit("20/minute")  # 迭代5：限流防密码爆破
def login(request: Request, req: AuthRequest):
    """登录：校验密码，签发 JWT"""
    user_id = users_db.verify_user(req.username, req.password)
    if user_id is None:
        # 不区分"用户不存在"和"密码错误"，防用户名枚举
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    logger.info("用户登录", extra={"user_id": user_id})
    return {"token": create_token(user_id), "username": req.username}


# ========== 鉴权依赖（所有 C 端受保护接口挂载）==========

_bearer = HTTPBearer(auto_error=False)  # 无 token 时不自动 403，由依赖统一返回 401


def get_current_user(cred: HTTPAuthorizationCredentials = Depends(_bearer)) -> int:
    """从 Authorization: Bearer <token> 解析 user_id，失败一律 401"""
    if cred is None:
        raise HTTPException(status_code=401, detail="未登录")
    try:
        return decode_token(cred.credentials)
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
