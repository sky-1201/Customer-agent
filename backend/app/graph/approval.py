"""审批节点（决策结论是换货/退货时，interrupt 暂停等人审批）

迭代4：决策结论"转人工"（AI 处理不了/置信度低）→ 建接管单，用户侧无缝进入人工通道。
迭代5：审批通过（换货/退货）→ 订单状态机流转到"退换货中"（留流转日志，可追溯）。
"""
from langgraph.types import interrupt

from app.db.approval import create_approval, update_approval
from app.db.catalog import transition_order_by_no
from app.graph.handover import escalate_to_handover
from app.graph.state import CustomerServiceState
from app.utils.logger import get_logger

logger = get_logger("approval_node")

# 需要人工审批的实质操作（不可逆，AI 不自动执行）
APPROVAL_CONCLUSIONS = {"换货", "退货"}

# 案件完结时清空的字段：订单号/澄清状态只在一个案件内有效，
# 不清空的话，同会话的下一个售后案件会静默继承旧订单号（张冠李戴核实错订单）
CASE_CLEANUP = {"order_no": None, "pending_clarify": None, "clarify_count": 0}


async def approval_node(state: CustomerServiceState) -> dict:
    """审批/回复节点：实质操作走 interrupt 审批，转人工建接管单，其他结论直接回复"""
    decision = state.get("final_decision")
    if decision is None:
        # decision 节点已回复过失败信息，这里只做案件清理，不重复回复
        return {**CASE_CLEANUP}

    # AI 处理不了（置信度低/核实失败等）→ 转人工接管（迭代4）
    if decision.conclusion == "转人工":
        await escalate_to_handover(state, reason="ai_escalate")
        logger.info("决策结论转人工，已建接管单")
        msg = decision.comfort_msg + "\n\n已为您转接人工客服，坐席会尽快接入，您可以直接留言补充情况。"
        return {"messages": [("assistant", msg)], **CASE_CLEANUP}

    # 非实质操作，直接回复
    if decision.conclusion not in APPROVAL_CONCLUSIONS:
        return {"messages": [("assistant", decision.comfort_msg)], **CASE_CLEANUP}

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
        # 实质操作落地：订单状态机流转 已完成 → 退换货中（迭代5，留流转日志）
        order_no = state.get("order_no")
        if order_no and state.get("user_id"):
            transition_order_by_no(
                order_no, state["user_id"], "退换货中",
                reason=f"审批单 #{approval_id} 批准（{decision.conclusion}）",
            )
        return {"messages": [("assistant", f"已为您办理：{decision.comfort_msg}")], **CASE_CLEANUP}

    reason = approval_result.get("reason", "未说明原因") if approval_result else "未说明原因"
    update_approval(approval_id, "rejected")
    logger.info("审批拒绝", extra={"approval_id": approval_id, "reason": reason})
    return {"messages": [("assistant", f"很抱歉，您的申请未通过：{reason}")], **CASE_CLEANUP}
