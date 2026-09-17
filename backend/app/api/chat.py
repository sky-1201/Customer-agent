"""对话接口（SSE 流式：实时推送 Agent 工作状态 + 最终回复）

SSE 事件协议（对应技术文档 7.4 节）：
  event: agent_status  data: {"agent": "tech", "msg": "正在查故障说明"}
  event: message       data: {"content": "..."}
  event: handover      data: {"status": "pending"|"active"}   ← 人工模式（迭代4）
  event: done          data: {}

迭代4（转人工）：会话有未完结接管单时，/chat 不进 AI 图——
用户消息写入 checkpoint 历史（保持单一事实源）并推送给坐席。
"""
import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from app.api.auth import get_current_user
from app.db.handover import get_open_handover_by_thread
from app.db.session import upsert_session
from app.graph.main import main_graph
from app.realtime import manager
from app.utils.limiter import limiter
from app.utils.logger import get_logger, set_trace_id

router = APIRouter()
logger = get_logger(__name__)

# 节点名 → (agent 标识, 展示文案)，用于 SSE 推送 Agent 工作状态
NODE_AGENT_MAP = {
    "router": ("analyzing", "正在分析您的问题"),
    "customer_agent": ("customer_agent", "正在为您查询"),
    "tech": ("tech", "正在查故障说明"),
    "aftersale": ("aftersale", "正在查政策+订单"),
    "decision": ("decision", "正在综合判断"),
    "ask_order_no": ("clarify", "正在确认订单信息"),
    "handover": ("handover", "正在为您转接人工客服"),
}


def sse(event: str, data: dict) -> str:
    """构造 SSE 事件"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def serialize_history(messages) -> list[dict]:
    """把 checkpoint 里的消息序列化成前端展示格式。

    sender 标记（additional_kwargs）区分消息来源：
    - human_agent：真人坐席（展示真人标识，绝不与 AI 互相伪装 —— PRD 硬要求）
    - system：系统提示（转人工/转回 AI 等身份切换提示）
    """
    history = []
    for m in messages:
        sender = getattr(m, "additional_kwargs", {}).get("sender")
        if sender == "human_agent":
            role = "human_agent"
        elif sender == "system":
            role = "system"
        else:
            role = {"human": "user", "ai": "assistant"}.get(getattr(m, "type", ""))
        content = getattr(m, "content", "")
        if role and isinstance(content, str) and content.strip():
            item = {"type": role, "content": content}
            if sender == "human_agent":
                item["agent_name"] = m.additional_kwargs.get("agent_name", "人工客服")
            history.append(item)
    return history


@router.get("/chat/history")
async def chat_history(session_id: str, user_id: int = Depends(get_current_user)):
    """会话历史（服务端 checkpoint 是唯一事实源，前端刷新/换设备都能恢复）。

    返回 messages + pending_approval（有未完成审批 → 前端直接启动轮询）
    + handover_status（有未完结接管 → 前端进入人工模式）。
    """
    thread_id = f"user_{user_id}_{session_id}"
    config = {"configurable": {"thread_id": thread_id}}
    snapshot = await main_graph.aget_state(config)
    handover = get_open_handover_by_thread(thread_id)

    return {
        "messages": serialize_history(snapshot.values.get("messages") or []),
        "pending_approval": bool(snapshot.next),
        "handover_status": handover["status"] if handover else None,
    }


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"  # 会话 ID（不含身份标识，身份只从 token 来）


@router.post("/chat")
@limiter.limit("30/minute")  # 迭代5：限流防刷（LLM 调用有成本）
async def chat(request: Request, req: ChatRequest, user_id: int = Depends(get_current_user)):
    # thread_id 由服务端拼接：user_{user_id}_{session_id}
    # 安全红线：用户身份只信 token，前端传任何 session_id 都碰不到别人的
    # 会话、checkpoint 和审批单（也无法 resume 别人的图）
    thread_id = f"user_{user_id}_{req.session_id}"

    # 用 thread_id 作为 trace_id，贯穿本次请求的所有日志
    set_trace_id(thread_id)
    logger.info(
        "收到对话请求",
        extra={"thread_id": thread_id, "user_id": user_id, "msg_len": len(req.message)},
    )

    # 会话建档/更新（迭代5：会话管理——首条消息建档，title 取首条消息截断）
    upsert_session(user_id, req.session_id, req.message)

    # 迭代4：会话处于人工接管模式（有待接管/接管中的接管单）→ 不进 AI 图
    handover = get_open_handover_by_thread(thread_id)
    if handover:
        return StreamingResponse(
            human_mode_stream(thread_id, req.message, handover),
            media_type="text/event-stream",
        )

    async def event_stream():
        config = {"configurable": {"thread_id": thread_id}}
        input_state = {
            "messages": [("user", req.message)],
            "thread_id": thread_id,
            "user_id": user_id,
        }

        # 1. 流式执行图，每个节点完成时推送 Agent 工作状态
        async for chunk in main_graph.astream(input_state, config):
            for node_name in chunk.keys():
                if node_name in NODE_AGENT_MAP:
                    agent, msg = NODE_AGENT_MAP[node_name]
                    yield sse("agent_status", {"agent": agent, "msg": msg})

        # 2. 拿最终状态：判断是 interrupt 暂停（等审批）还是正常完成
        snapshot = await main_graph.aget_state(config)
        if snapshot.next:
            # 图暂停（interrupt 等审批），返回等待提示
            final = "您的申请已提交，正在等待人工审核，请稍候..."
            logger.info("对话中断（等待审批）", extra={"thread_id": thread_id})
        else:
            messages = snapshot.values.get("messages") or []
            final = messages[-1].content if messages else "抱歉，处理失败。"
            logger.info(
                "对话完成",
                extra={"thread_id": thread_id, "reply_len": len(final or "")},
            )

        yield sse("message", {"content": final})
        yield sse("done", {})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


async def human_mode_stream(thread_id: str, message: str, handover: dict):
    """人工模式：用户消息写入 checkpoint 历史 + 实时推送给接管坐席（AI 不参与）"""
    config = {"configurable": {"thread_id": thread_id}}
    await main_graph.aupdate_state(
        config, {"messages": [HumanMessage(content=message)]}
    )
    logger.info(
        "人工模式留言",
        extra={"thread_id": thread_id, "handover_id": handover["id"], "status": handover["status"]},
    )
    if handover["status"] == "active":
        await manager.broadcast_agents(
            {"type": "user_message", "handover_id": handover["id"], "content": message}
        )
    # 通知前端当前处于人工模式（类型信息放 data 的 key 里——前端 SSE 解析器只读 data，
    # 与 agent_status/message 事件的约定一致），前端据此隐藏"处理中断"兜底提示
    yield sse("handover", {"handover": handover["status"]})
    yield sse("done", {})
