"""对话接口（SSE 流式返回）"""
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.graph.main import main_graph
from app.utils.logger import get_logger, set_trace_id

router = APIRouter()
logger = get_logger(__name__)


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
        result = await main_graph.ainvoke(
            {"messages": [("user", req.message)], "thread_id": req.thread_id}, config
        )
        # 检测 interrupt：图被暂停（等审批）时，state 里有 __interrupt__ 标记，
        # 此时不应把最后一条消息（用户消息）当回复，而应返回"等待审核"提示
        if result.get("__interrupt__"):
            final = "您的申请已提交，正在等待人工审核，请稍候..."
            logger.info("对话中断（等待审批）", extra={"thread_id": req.thread_id})
        else:
            final = result["messages"][-1].content
            logger.info(
                "对话完成",
                extra={"thread_id": req.thread_id, "reply_len": len(final or "")},
            )
        yield f"data: {json.dumps({'content': final}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
