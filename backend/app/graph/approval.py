"""审批节点（决策结论是换货/退货时，interrupt 暂停等人审批）"""
from langgraph.types import interrupt

from app.db.approval import create_approval, update_approval
from app.graph.state import CustomerServiceState
from app.utils.logger import get_logger

logger = get_logger("approval_node")

# 需要人工审批的实质操作（不可逆，AI 不自动执行）
APPROVAL_CONCLUSIONS = {"换货", "退货"}


def approval_node(state: CustomerServiceState) -> dict:
    """审批/回复节点：实质操作走 interrupt 审批，其他结论直接回复"""
    decision = state.get("final_decision")
    if decision is None:
        return {"messages": [("assistant", "抱歉，处理失败，请稍后再试。")]}

    # 非实质操作，直接回复
    if decision.conclusion not in APPROVAL_CONCLUSIONS:
        return {"messages": [("assistant", decision.comfort_msg)]}

    # 实质操作：写审批单 + interrupt 暂停
    approval_id = create_approval(state, decision)
    logger.info("触发人工审批", extra={"approval_id": approval_id, "conclusion": decision.conclusion})

    # interrupt 暂停：状态持久化到 checkpoint，等坐席在管理端审批
    approval_result = interrupt({"approval_id": approval_id})

    # resume 后，approval_result 是坐席传入的决策 {"action": "approve"/"reject", "reason": ...}
    action = approval_result.get("action") if approval_result else "approve"

    if action == "approve":
        update_approval(approval_id, "approved")
        logger.info("审批通过", extra={"approval_id": approval_id})
        return {"messages": [("assistant", f"已为您办理：{decision.comfort_msg}")]}

    reason = approval_result.get("reason", "未说明原因") if approval_result else "未说明原因"
    update_approval(approval_id, "rejected")
    logger.info("审批拒绝", extra={"approval_id": approval_id, "reason": reason})
    return {"messages": [("assistant", f"很抱歉，您的申请未通过：{reason}")]}
