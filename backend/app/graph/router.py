"""分流器：规则快筛 + 小模型分类 + 置信度兜底（对应技术文档第3节）"""
from typing import Literal

from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from app.config import DASHSCOPE_API_KEY, DASHSCOPE_BASE_URL, ROUTER_MODEL
from app.graph.state import CustomerServiceState
from app.utils.logger import get_logger

logger = get_logger("router")

# 规则快筛关键词（第1层，零 LLM 调用）
HIGH_RISK_KEYWORDS = ["投诉", "曝光", "12315", "消协", "差评", "退一赔三"]
REFUND_KEYWORDS = ["退款", "退货", "换货", "换新", "赔偿"]
# 纯问候语（简单打招呼，直接 simple，避免模糊问候被低置信度兜底成 complex）
GREETINGS = {"你好", "您好", "在吗", "在不在", "hi", "hello", "哈喽", "嗨"}


class IntentClassification(BaseModel):
    intent: Literal["simple", "complex", "complaint"] = Field(description="意图分类")
    confidence: float = Field(ge=0, le=1, description="0-1 置信度")
    risk_signals: list[str] = Field(default_factory=list, description="命中的风险信号")
    reasoning: str = Field(description="为什么这样分类")


# 分流用「小模型」（qwen-flash，分类是简单任务，不需要强模型）
router_llm = ChatOpenAI(
    api_key=DASHSCOPE_API_KEY,
    base_url=DASHSCOPE_BASE_URL,
    model=ROUTER_MODEL,
    temperature=0,
).with_structured_output(IntentClassification, method="function_calling")

ROUTER_PROMPT = """你是客服分流器，判断用户消息应该走哪条处理流程。

分类标准：
- simple：简单的 FAQ、售前咨询、产品推荐、政策咨询（如"过保了还能修吗"），单轮能回答
- complex：涉及退换货判断，需要技术+政策+订单多维度核实（如"修两次要换货"）
- complaint：投诉、威胁、强烈负面情绪（如"我要投诉到12315"）

判断规则：
- 重点判断最后一条用户消息的意图
- 纯问候语（如"你好""在吗"）→ simple，且给出高置信度
- 命中退款/退货/换货等诉求 → complex
- 命中投诉/威胁情绪 → complaint
- 仅政策咨询（不涉及退换货判断）→ simple
- 不确定就给出低置信度
"""


def rule_triage(text: str) -> str | None:
    """规则快筛：纯问候 → simple；高险词 → complaint；退款词 → complex"""
    t = text.strip().lower()
    # 纯问候 → simple（模糊问候 LLM 置信度低，避免被兜底成 complex 触发误审批）
    if t in GREETINGS or (len(t) <= 5 and any(g in t for g in GREETINGS)):
        return "simple"
    if any(k in text for k in HIGH_RISK_KEYWORDS):
        return "complaint"
    if any(k in text for k in REFUND_KEYWORDS):
        return "complex"
    return None


def router_node(state: CustomerServiceState) -> dict:
    """分流节点：三层分流（规则 → LLM 分类 → 置信度兜底）"""
    last_user = state["messages"][-1].content

    # 第1层：规则快筛
    rule_result = rule_triage(last_user)
    if rule_result:
        logger.info(
            "分流结果",
            extra={"intent": rule_result, "source": "rule", "query": last_user[:30]},
        )
        return {
            "intent": rule_result,
            "intent_confidence": 1.0,
            "risk_signals": [rule_result],
        }

    # 第2层：LLM 分类（小模型 + 结构化输出）
    try:
        result = router_llm.invoke(
            [SystemMessage(content=ROUTER_PROMPT), ("user", last_user)]
        )
    except Exception as e:
        # 分类失败 → 兜底走复杂流程（稳妥，宁可错杀不可放过）
        logger.warning("分流失败，兜底走 complex", extra={"error": type(e).__name__})
        return {"intent": "complex", "intent_confidence": 0.0, "risk_signals": []}

    # 第3层：置信度兜底
    if result.intent == "complaint":
        intent = "complaint"
    elif result.confidence < 0.7:
        intent = "complex"  # 低置信 → 复杂流程
    else:
        intent = result.intent

    logger.info(
        "分流结果",
        extra={
            "intent": intent,
            "confidence": result.confidence,
            "source": "llm",
            "signals": result.risk_signals,
            "query": last_user[:30],
        },
    )
    return {
        "intent": intent,
        "intent_confidence": result.confidence,
        "risk_signals": result.risk_signals,
    }
