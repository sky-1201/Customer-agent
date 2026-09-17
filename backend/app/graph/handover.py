"""转人工节点（迭代4：complaint / 澄清失败 → 写接管单 + 通知坐席）

四路触发汇聚于此（或复用 escalate_to_handover）：
1. 投诉意图（规则/LLM 分流 complaint）
2. 用户主动说"转人工"（HANDOVER_KEYWORDS → complaint 分支）
3. 澄清超限（clarify_overflow）
4. 决策"转人工"结论（approval 节点调 escalate_to_handover，reason=ai_escalate）
"""
from app.db.handover import create_handover, get_open_handover_by_thread
from app.graph.state import CustomerServiceState
from app.graph.utils import recent_user_texts
from app.realtime import manager
from app.utils.logger import get_logger

logger = get_logger("handover_node")


def _snapshot_context(state: CustomerServiceState) -> dict:
    """AI 已核实信息快照（接管交接：坐席不让用户重复描述）"""
    ctx = {}
    for key in ("tech_result", "aftersale_result", "final_decision"):
        v = state.get(key)
        ctx[key] = v.model_dump() if v else None
    return ctx


async def escalate_to_handover(state: CustomerServiceState, reason: str) -> int:
    """建接管单 + WS 通知坐席端。幂等：同一会话已有未完结接管单则复用（用户连发投诉不重复建单）"""
    thread_id = state.get("thread_id") or ""
    existing = get_open_handover_by_thread(thread_id)
    if existing:
        return existing["id"]

    handover_id = create_handover(
        thread_id=thread_id,
        user_id=state.get("user_id"),
        reason=reason,
        user_request=recent_user_texts(state, n=2)[:500],
        agent_context=_snapshot_context(state),
    )
    logger.info("转人工：接管单已入队", extra={"handover_id": handover_id, "reason": reason})
    # 通知坐席端刷新待接管队列
    await manager.broadcast_agents({"type": "queue_update"})
    return handover_id


async def handover_node(state: CustomerServiceState) -> dict:
    """complaint 分支：转人工（写接管单 → 待接管队列 → 回复用户）"""
    signals = state.get("risk_signals") or []
    if "clarify_overflow" in signals:
        reason = "clarify_overflow"
    elif "complaint_during_clarify" in signals or state.get("intent") == "complaint":
        reason = "complaint"
    else:
        reason = "user_request"

    had_open = get_open_handover_by_thread(state.get("thread_id") or "") is not None
    await escalate_to_handover(state, reason)

    if had_open:
        text = "人工客服接入中，您可以直接留言补充情况，坐席接管后都能看到。"
    else:
        text = (
            "已为您转接人工客服，请稍候（坐席接入中）。"
            "您可以直接留言补充情况，坐席接管后都能看到，无需重复描述。"
        )
    return {"messages": [("assistant", text)]}
