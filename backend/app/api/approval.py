"""管理端审批接口（待审批列表 + 提交审批触发 resume）

鉴权说明（迭代1 决策）：管理端接口（列表/提交）暂不设防，由演示者本地使用，
迭代5 安全加固时补坐席鉴权。C 端轮询接口（/approvals/status）必须登录 + 校验归属。
"""
from fastapi import APIRouter, Depends, HTTPException
from langgraph.types import Command
from pydantic import BaseModel

from app.api.auth import get_current_user
from app.db.approval import get_approval, get_approval_by_thread, list_approvals, update_approval
from app.graph.main import main_graph
from app.utils.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


class ApprovalRequest(BaseModel):
    action: str = "approve"  # approve / reject
    reason: str = ""


@router.get("/approvals")
def get_approvals():
    """待审批列表（管理端）"""
    return list_approvals()


@router.get("/approvals/status")
async def approval_status(session_id: str, user_id: int = Depends(get_current_user)):
    """客户端轮询审批结果（收到"等待审核"后定时查询）

    安全红线：thread_id 永远由服务端用 token 里的 user_id 拼接，
    前端只传 session_id——物理上无法伪造别人的 thread_id 来轮询审批结果。
    """
    thread_id = f"user_{user_id}_{session_id}"

    approval = get_approval_by_thread(thread_id)
    if approval is None:
        return {"status": "none"}  # 尚未触发审批

    if approval["status"] == "pending":
        return {"status": "pending"}  # 还在等审批

    # 已审批：从 checkpoint 读最终回复（resume 后 approval 节点写入的 messages）
    config = {"configurable": {"thread_id": thread_id}}
    snapshot = await main_graph.aget_state(config)
    messages = snapshot.values.get("messages") or []
    reply = messages[-1].content if messages else ""
    return {"status": approval["status"], "reply": reply}


@router.post("/approvals/{approval_id}")
async def submit_approval(approval_id: int, req: ApprovalRequest):
    """提交审批：更新状态 + resume 恢复暂停的图"""
    approval = get_approval(approval_id)
    if not approval:
        return {"error": "审批单不存在"}

    thread_id = approval["thread_id"]
    status = "approved" if req.action == "approve" else "rejected"
    update_approval(approval_id, status)

    logger.info(
        "坐席提交审批",
        extra={"approval_id": approval_id, "action": req.action, "thread_id": thread_id},
    )

    # resume 恢复 interrupt 暂停的图，把坐席的决策传回 approval 节点
    config = {"configurable": {"thread_id": thread_id}}
    resume_value = {"action": req.action, "reason": req.reason}
    result = await main_graph.ainvoke(Command(resume=resume_value), config)

    return {"status": status, "reply": result["messages"][-1].content}
