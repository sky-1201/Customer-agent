"""图节点共用的小工具（订单号提取 / 用户诉求拼接）—— 迭代3"""
import re

from app.graph.state import CustomerServiceState

# 订单号格式：O- + 数字（如 O-001、O-20260914103015999）
ORDER_NO_PATTERN = re.compile(r"O-\d+")


def extract_order_no(text: str) -> str | None:
    """从文本提取订单号（O- 开头 + 数字），没有返回 None"""
    m = ORDER_NO_PATTERN.search(text)
    return m.group() if m else None


def extract_order_no_from_history(messages: list) -> str | None:
    """从消息历史提取订单号（从后往前找，用户最新给的优先）"""
    for m in reversed(messages):
        if getattr(m, "type", "") == "human":
            found = extract_order_no(m.content or "")
            if found:
                return found
    return None


def recent_user_texts(state: CustomerServiceState, n: int = 3) -> str:
    """拼接最近 n 条用户消息作为完整诉求。

    澄清场景下，最后一条用户消息只是订单号回答（如"O-001"），
    故障描述在前面——单看最后一条会丢上下文。
    """
    texts = [m.content for m in state["messages"] if getattr(m, "type", "") == "human"]
    return "\n".join(texts[-n:])
