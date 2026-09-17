"""WebSocket 连接管理（迭代4：坐席接管的实时推送通道）

单进程内存管理（本项目单机部署够用）。
若未来多实例部署，需换成 Redis pub/sub 做跨进程广播，本模块接口保持不变。
"""
from fastapi import WebSocket

from app.utils.logger import get_logger

logger = get_logger("ws_manager")


class ConnectionManager:
    def __init__(self):
        # thread_id → 该会话的用户端连接（同一会话可能开多个标签页）
        self.user_conns: dict[str, set[WebSocket]] = {}
        # 坐席端连接集合（管理端接管台）
        self.agent_conns: set[WebSocket] = set()

    async def connect_user(self, thread_id: str, ws: WebSocket):
        await ws.accept()
        self.user_conns.setdefault(thread_id, set()).add(ws)
        logger.info("用户 WS 接入", extra={"thread_id": thread_id})

    def disconnect_user(self, thread_id: str, ws: WebSocket):
        conns = self.user_conns.get(thread_id)
        if conns:
            conns.discard(ws)
            if not conns:
                self.user_conns.pop(thread_id, None)

    async def connect_agent(self, ws: WebSocket):
        await ws.accept()
        self.agent_conns.add(ws)
        logger.info("坐席 WS 接入", extra={"agent_conns": len(self.agent_conns)})

    def disconnect_agent(self, ws: WebSocket):
        self.agent_conns.discard(ws)

    async def send_to_user(self, thread_id: str, data: dict):
        """推送事件给某会话的用户端（坐席消息 / 接管状态变化）"""
        for ws in list(self.user_conns.get(thread_id, ())):
            try:
                await ws.send_json(data)
            except Exception:
                self.disconnect_user(thread_id, ws)  # 死连接清理

    async def broadcast_agents(self, data: dict):
        """广播事件给所有坐席端（新接管单 / 用户留言）"""
        for ws in list(self.agent_conns):
            try:
                await ws.send_json(data)
            except Exception:
                self.disconnect_agent(ws)


manager = ConnectionManager()
