"""管理端接管接口（迭代4：待接管队列 + 接管 + 坐席发消息 + 结束/转回AI）

设计：坐席操作走 REST，实时推送走 WS（/ws/agent 收队列和用户留言）。
接管期间双方消息都写入 checkpoint 的 messages 通道——对话历史保持单一事实源，
"转回 AI"后 AI 能完整看到人工沟通过程。

鉴权说明（迭代5）：管理端接口要求登录（任一用户），坐席角色体系留待后续。
"""
from fastapi import APIRouter, Depends, HTTPException

from app.api.auth import get_current_user
from langchain_core.messages import AIMessage
from pydantic import BaseModel

from app.api.chat import serialize_history
from app.db import handover as handover_db
from app.graph.main import main_graph
from app.realtime import manager
from app.utils.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)

AGENT_NAME = "人工客服"  # 单坐席演示；多坐席体系留迭代5


def _get_or_404(handover_id: int) -> dict:
    h = handover_db.get_handover(handover_id)
    if not h:
        raise HTTPException(status_code=404, detail="接管单不存在")
    return h


async def _append_system_message(thread_id: str, text: str):
    """往会话历史写系统提示（身份切换提示：转人工/转回 AI）"""
    config = {"configurable": {"thread_id": thread_id}}
    await main_graph.aupdate_state(
        config,
        {"messages": [AIMessage(content=text, additional_kwargs={"sender": "system"})]},
    )


@router.get("/handovers")
def list_handovers(status: str | None = None, user_id: int = Depends(get_current_user)):
    """接管单列表（pending 待接管 / active 接管中，pending 排队先来的先接）"""
    return handover_db.list_handovers(status)


@router.get("/handovers/{handover_id}")
async def handover_detail(handover_id: int, user_id: int = Depends(get_current_user)):
    """接管详情：接管单（含 AI 已核实信息快照）+ 完整对话历史"""
    h = _get_or_404(handover_id)
    config = {"configurable": {"thread_id": h["thread_id"]}}
    snapshot = await main_graph.aget_state(config)
    return {
        "handover": h,
        "history": serialize_history(snapshot.values.get("messages") or []),
    }


@router.post("/handovers/{handover_id}/take")
async def take_handover(handover_id: int, user_id: int = Depends(get_current_user)):
    """坐席接管（pending → active，并发安全：已被接管的返回 409）"""
    _get_or_404(handover_id)
    if not handover_db.take_handover(handover_id):
        raise HTTPException(status_code=409, detail="该会话已被接管或已关闭")

    h = handover_db.get_handover(handover_id)
    await _append_system_message(h["thread_id"], "人工客服已接入，现在由真人客服为您服务")
    await manager.send_to_user(
        h["thread_id"],
        {"type": "handover_status", "status": "active", "msg": "人工客服已接入"},
    )
    return {"status": "active"}


class AgentMessageRequest(BaseModel):
    content: str


@router.post("/handovers/{handover_id}/messages")
async def send_agent_message(handover_id: int, req: AgentMessageRequest, user_id: int = Depends(get_current_user)):
    """坐席发消息 → 写入会话历史（带真人标识）+ WS 实时推给用户"""
    h = _get_or_404(handover_id)
    if h["status"] != "active":
        raise HTTPException(status_code=409, detail="请先接管再发送消息")

    config = {"configurable": {"thread_id": h["thread_id"]}}
    await main_graph.aupdate_state(
        config,
        {"messages": [AIMessage(
            content=req.content,
            additional_kwargs={"sender": "human_agent", "agent_name": AGENT_NAME},
        )]},
    )
    await manager.send_to_user(
        h["thread_id"],
        {"type": "human_message", "content": req.content, "agent_name": AGENT_NAME},
    )
    logger.info("坐席发送消息", extra={"handover_id": handover_id, "msg_len": len(req.content)})
    return {"status": "sent"}


@router.post("/handovers/{handover_id}/return")
async def return_to_ai(handover_id: int, user_id: int = Depends(get_current_user)):
    """转回 AI（active → returned）：后续用户消息恢复走 AI 图"""
    h = _get_or_404(handover_id)
    if not handover_db.close_handover(handover_id, returned=True):
        raise HTTPException(status_code=409, detail="该会话不在接管中")

    await _append_system_message(h["thread_id"], "人工服务已结束，已为您转回智能客服")
    await manager.send_to_user(
        h["thread_id"],
        {"type": "handover_status", "status": "returned", "msg": "已转回智能客服"},
    )
    return {"status": "returned"}


@router.post("/handovers/{handover_id}/close")
async def close_handover(handover_id: int, user_id: int = Depends(get_current_user)):
    """结束会话（active → closed）"""
    h = _get_or_404(handover_id)
    if not handover_db.close_handover(handover_id, returned=False):
        raise HTTPException(status_code=409, detail="该会话不在接管中")

    await _append_system_message(h["thread_id"], "人工服务已结束，感谢您的咨询")
    await manager.send_to_user(
        h["thread_id"],
        {"type": "handover_status", "status": "closed", "msg": "人工服务已结束"},
    )
    return {"status": "closed"}
