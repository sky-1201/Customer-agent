"""WebSocket 端点（迭代4：坐席接管的双向实时通道）

- /ws/chat：用户端。接收坐席消息 + 接管状态变化。鉴权用 token 查询参数
  （WS 握手不支持自定义头，token 从 query 传）。
- /ws/agent：坐席端。接收新接管单通知 + 接管中会话的用户留言。

两个端点都只收不发（客户端消息走 REST POST），WS 纯做服务端→客户端推送。
"""
import jwt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.realtime import manager
from app.utils.logger import get_logger
from app.utils.security import decode_token

router = APIRouter()
logger = get_logger("ws")


@router.websocket("/ws/chat")
async def user_chat_ws(ws: WebSocket, session_id: str = "", token: str = ""):
    """用户端实时通道（按 token 鉴权，thread_id 服务端拼接，防越权收听别人会话）"""
    try:
        user_id = decode_token(token)
    except jwt.PyJWTError:
        # 先 accept 再带码关闭，客户端才能收到明确的 4401（未认证）
        await ws.accept()
        await ws.close(code=4401)
        return
    thread_id = f"user_{user_id}_{session_id}"
    await manager.connect_user(thread_id, ws)
    try:
        while True:
            await ws.receive_text()  # 仅用于断开检测/保活，用户消息走 POST /api/chat
    except WebSocketDisconnect:
        manager.disconnect_user(thread_id, ws)


@router.websocket("/ws/agent")
async def agent_ws(ws: WebSocket, token: str = ""):
    """坐席端实时通道（迭代5：要求登录 token，坐席角色体系留待后续）"""
    try:
        decode_token(token)
    except jwt.PyJWTError:
        await ws.accept()
        await ws.close(code=4401)
        return
    await manager.connect_agent(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect_agent(ws)
