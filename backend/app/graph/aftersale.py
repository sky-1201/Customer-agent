"""售后核实节点（complex 分支的一路：查政策 + 查订单 → 输出 AftersaleResult）"""
from datetime import date

from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI

from app.config import AGENT_MODEL, DASHSCOPE_API_KEY, DASHSCOPE_BASE_URL
from app.graph.state import CustomerServiceState
from app.kb.order import format_order, query_order
from app.kb.policy import query_full_policy
from app.models.structured import AftersaleResult
from app.utils.logger import get_logger

logger = get_logger("aftersale_node")

aftersale_llm = ChatOpenAI(
    api_key=DASHSCOPE_API_KEY,
    base_url=DASHSCOPE_BASE_URL,
    model=AGENT_MODEL,
    temperature=0,
).with_structured_output(AftersaleResult, method="function_calling")

AFTERSALE_PROMPT = """你是售后政策核实专家。根据政策条款、订单信息和用户诉求，核实售后条件。

判断要点：
- order_valid：订单是否存在
- in_warranty：是否在三包期内（根据下单时间和保修政策判断）
- repair_count：维修次数（从维修记录数）
- policy_applicable：政策是否适用（能否换货/退货）
- confidence：置信度

注意：不要编造订单信息和政策条款，只根据提供的内容判断。
"""

# 演示场景：核心订单 O-001（小新 Pro 16，修两次换货）
# TODO: 后续支持多订单时，改为从 state 动态获取订单号
DEMO_ORDER_NO = "O-001"


def aftersale_node(state: CustomerServiceState) -> dict:
    """售后核实：查完整政策 + 查订单 → 结构化输出 AftersaleResult"""
    user_msg = state["messages"][-1].content

    # 1. 查完整政策 + 订单信息（结构化）
    full_policy = query_full_policy()
    order = query_order(DEMO_ORDER_NO)

    if order is None:
        result = AftersaleResult(
            order_valid=False, in_warranty=False, repair_count=0,
            policy_applicable=False, policy_ref="订单不存在", confidence=0.0,
        )
        logger.warning("售后核实：订单不存在", extra={"order_no": DEMO_ORDER_NO})
        return {"aftersale_result": result}

    # 2. LLM 结构化输出（判断 in_warranty / repair_count / policy_applicable）
    try:
        result = aftersale_llm.invoke(
            [
                SystemMessage(content=AFTERSALE_PROMPT),
                (
                    "user",
                    f"用户诉求：{user_msg}\n\n三包政策：\n{full_policy}\n\n"
                    f"订单信息：\n{format_order(order)}\n\n当前日期：{date.today()}",
                ),
            ]
        )
    except Exception as e:
        logger.error("售后核实失败", extra={"error": type(e).__name__}, exc_info=True)
        result = AftersaleResult(
            order_valid=False, in_warranty=False, repair_count=0,
            policy_applicable=False, policy_ref="核实失败", confidence=0.0,
        )

    # 3. 订单号、购买时间、政策从数据库【精确覆盖】（防 LLM 抄错/提取不全）
    result.order_no = order["order_no"]
    result.purchase_date = order["purchase_date"]
    result.policy_ref = full_policy

    logger.info(
        "售后核实完成",
        extra={
            "order_no": result.order_no,
            "in_warranty": result.in_warranty,
            "repair_count": result.repair_count,
            "policy_applicable": result.policy_applicable,
        },
    )
    return {"aftersale_result": result}
