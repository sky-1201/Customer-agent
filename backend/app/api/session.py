"""会话管理接口（迭代5：历史会话列表 / 归档）"""
from fastapi import APIRouter, Depends, HTTPException

from app.api.auth import get_current_user
from app.db import session as session_db
from app.utils.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.get("/sessions")
def list_sessions(user_id: int = Depends(get_current_user)):
    """当前用户的会话列表（未归档，最近活跃在前）"""
    return session_db.list_sessions(user_id)


@router.delete("/sessions/{session_id}")
def archive_session(session_id: str, user_id: int = Depends(get_current_user)):
    """归档会话（只能归档自己的；归档只是隐藏，checkpoint 历史仍保留）"""
    if not session_db.archive_session(user_id, session_id):
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"status": "archived"}
