"""技术诊断节点（complex 分支的一路：查故障 + 维修记录 → 输出 TechResult）"""
from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI

from app.config import AGENT_MODEL, DASHSCOPE_API_KEY, DASHSCOPE_BASE_URL
from app.graph.state import CustomerServiceState
from app.kb.order import format_order, query_order
from app.kb.search import search_troubleshooting
from app.models.structured import TechResult
from app.utils.logger import get_logger

logger = get_logger("tech_node")

tech_llm = ChatOpenAI(
    api_key=DASHSCOPE_API_KEY,
    base_url=DASHSCOPE_BASE_URL,
    model=AGENT_MODEL,
    temperature=0,
).with_structured_output(TechResult, method="function_calling")

TECH_PROMPT = """你是笔记本技术诊断专家。根据用户描述、故障知识和维修记录，做技术诊断。

重点判断：
- fault：故障现象是什么
- same_fault：多次维修是否属于"同一故障"（依据维修记录里每次维修的故障描述对比判断）
- cause：可能的故障原因
- confidence：置信度

注意：same_fault 的判断要依据维修记录。如果维修记录显示多次维修是同一故障现象（如都是蓝屏），则 same_fault=True。
"""

# 演示场景：核心订单 O-001（同 aftersale 一路，后续支持多订单时改为动态获取）
DEMO_ORDER_NO = "O-001"


def tech_node(state: CustomerServiceState) -> dict:
    """技术诊断：查故障说明 + 维修记录 → 结构化输出 TechResult"""
    user_msg = state["messages"][-1].content

    # 1. 查故障说明（语义检索）+ 维修记录（判断"是否同一故障"的关键依据）
    fault_info = search_troubleshooting(user_msg)
    order = query_order(DEMO_ORDER_NO)
    repair_info = format_order(order) if order else "订单不存在"

    # 2. 结构化输出 TechResult
    try:
        result = tech_llm.invoke(
            [
                SystemMessage(content=TECH_PROMPT),
                (
                    "user",
                    f"用户诉求：{user_msg}\n\n故障知识：{fault_info}\n\n维修记录：\n{repair_info}",
                ),
            ]
        )
    except Exception as e:
        logger.error("技术诊断失败", extra={"error": type(e).__name__}, exc_info=True)
        result = TechResult(fault="未知", same_fault=False, cause="诊断失败", confidence=0.0)

    logger.info(
        "技术诊断完成",
        extra={"fault": result.fault, "same_fault": result.same_fault, "confidence": result.confidence},
    )
    return {"tech_result": result}
