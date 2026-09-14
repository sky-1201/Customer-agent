"""槽位澄清节点：缺订单号时主动追问（迭代3）

采用《迭代01》5.4 节的方案 B（自然多轮澄清，企业更常用）：
不用 interrupt 挂起，直接回复追问 + 在 state 记 pending_clarify，
用户下一条消息由 router 优先按澄清回答处理。
"""
from app.graph.state import CustomerServiceState
from app.utils.logger import get_logger

logger = get_logger("clarify_node")


def ask_order_no_node(state: CustomerServiceState) -> dict:
    """追问订单号。首次问和再次追问的话术不同（再次给更明确的格式指引）"""
    count = state.get("clarify_count") or 0
    if count == 0:
        text = (
            "为了帮您核实售后情况，请提供一下您的订单号（O- 开头），"
            "您可以在「我的订单」页面查看。"
        )
    else:
        text = (
            "还是没有识别到订单号。请直接输入 O- 开头的订单号"
            "（如 O-20260315100000），在「我的订单」页面可以找到。"
        )
    logger.info("追问订单号", extra={"clarify_round": count + 1})
    return {"messages": [("assistant", text)], "pending_clarify": "order_no"}
