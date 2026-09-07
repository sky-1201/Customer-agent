"""管理端审批接口（待审批列表 + 提交审批触发 resume）"""
from fastapi import APIRouter
from langgraph.types import Command
from pydantic import BaseModel

from app.db.approval import get_approval, list_approvals, update_approval
from app.graph.main import main_graph
from app.utils.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


class ApprovalRequest(BaseModel):
    action: str = "approve"  # approve / reject
    reason: str = ""


@router.get("/approvals")
def get_approvals():
    """待审批列表"""
    return list_approvals()


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
