"""决策节点（交叉核验：读技术诊断 + 售后核实 → 输出 FinalDecision）"""
from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI

from app.config import AGENT_MODEL, DASHSCOPE_API_KEY, DASHSCOPE_BASE_URL
from app.graph.state import CustomerServiceState
from app.models.structured import FinalDecision
from app.utils.logger import get_logger

logger = get_logger("decision_node")

decision_llm = ChatOpenAI(
    api_key=DASHSCOPE_API_KEY,
    base_url=DASHSCOPE_BASE_URL,
    model=AGENT_MODEL,
    temperature=0,
).with_structured_output(FinalDecision, method="function_calling")

DECISION_PROMPT = """你是售后决策专家。根据技术诊断和售后核实的结果，做交叉核验，给出最终结论。

交叉核验规则（字段比对）：
- same_fault=True 且 repair_count>=2 且 policy_applicable=True → 结论"换货"
- same_fault=False（不是同一故障）→ 结论"维修"或"不满足"
- order_valid=False 或任一 confidence 很低 → 结论"转人工"
- 结论必须有政策依据（policy_ref）
- comfort_msg 要安抚用户情绪，说明结论和依据

重要：不要折中含糊，基于字段明确判断。
"""


def decision_node(state: CustomerServiceState) -> dict:
    """交叉核验：读 tech_result + aftersale_result → 输出 FinalDecision"""
    tech = state.get("tech_result")
    aftersale = state.get("aftersale_result")

    if tech is None or aftersale is None:
        logger.warning(
            "交叉核验缺少输入",
            extra={"tech": tech is not None, "aftersale": aftersale is not None},
        )
        return {"messages": [("assistant", "抱歉，核实信息不完整，请稍后再试。")]}

    try:
        result = decision_llm.invoke(
            [
                SystemMessage(content=DECISION_PROMPT),
                (
                    "user",
                    f"技术诊断：{tech.model_dump_json()}\n\n售后核实：{aftersale.model_dump_json()}",
                ),
            ]
        )
    except Exception as e:
        logger.error("决策失败", extra={"error": type(e).__name__}, exc_info=True)
        result = FinalDecision(
            conclusion="转人工", confidence=0.0, reasoning="决策失败",
            policy_ref="", comfort_msg="抱歉，请稍后再试。",
        )

    logger.info(
        "决策完成",
        extra={"conclusion": result.conclusion, "confidence": result.confidence},
    )
    # 只存 final_decision，不直接回复（回复统一由 approval 节点处理，实质操作需先审批）
    return {"final_decision": result}
