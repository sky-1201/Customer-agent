"""对话接口（SSE 流式：实时推送 Agent 工作状态 + 最终回复）

SSE 事件协议（对应技术文档 7.4 节）：
  event: agent_status  data: {"agent": "tech", "msg": "正在查故障说明"}
  event: message       data: {"content": "..."}
  event: done          data: {}
"""
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.graph.main import main_graph
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
}


def sse(event: str, data: dict) -> str:
    """构造 SSE 事件"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


class ChatRequest(BaseModel):
    message: str
    thread_id: str = "demo"  # 会话 ID，多轮对话用同一个


@router.post("/chat")
async def chat(req: ChatRequest):
    # 用 thread_id 作为 trace_id，贯穿本次请求的所有日志
    set_trace_id(req.thread_id)
    logger.info(
        "收到对话请求",
        extra={"thread_id": req.thread_id, "msg_len": len(req.message)},
    )

    async def event_stream():
        config = {"configurable": {"thread_id": req.thread_id}}
        input_state = {"messages": [("user", req.message)], "thread_id": req.thread_id}

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
            logger.info("对话中断（等待审批）", extra={"thread_id": req.thread_id})
        else:
            messages = snapshot.values.get("messages") or []
            final = messages[-1].content if messages else "抱歉，处理失败。"
            logger.info(
                "对话完成",
                extra={"thread_id": req.thread_id, "reply_len": len(final or "")},
            )

        yield sse("message", {"content": final})
        yield sse("done", {})

    return StreamingResponse(event_stream(), media_type="text/event-stream")
