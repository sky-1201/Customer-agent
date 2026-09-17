"""分流器：规则快筛 + 小模型分类 + 置信度兜底（对应技术文档第3节）

迭代3 新增：槽位澄清处理（pending_clarify）——用户没给订单号时 Agent 主动追问，
用户回复后优先按"澄清回答"处理，不重新分类（见《迭代01》5.4 节，方案B 自然多轮）。
"""
from typing import Literal

from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from app.config import DASHSCOPE_API_KEY, DASHSCOPE_BASE_URL, ROUTER_MODEL
from app.graph.state import CustomerServiceState
from app.graph.utils import extract_order_no
from app.utils.logger import get_logger

logger = get_logger("router")

# 规则快筛关键词（第1层，零 LLM 调用）
HIGH_RISK_KEYWORDS = ["投诉", "曝光", "12315", "消协", "差评", "退一赔三"]
REFUND_KEYWORDS = ["退款", "退货", "换货", "换新", "赔偿"]
# 主动转人工（迭代4：和投诉一样进 handover 分支）
HANDOVER_KEYWORDS = ["转人工", "人工客服", "真人客服", "人工服务", "真人"]
# 纯问候语（简单打招呼，直接 simple，避免模糊问候被低置信度兜底成 complex）
GREETINGS = {"你好", "您好", "在吗", "在不在", "hi", "hello", "哈喽", "嗨"}

# 澄清上限：最多追问 2 次，超限降级转人工（防死循环，澄清防线①）
MAX_CLARIFY = 2


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
    """规则快筛：纯问候 → simple；高险词/主动转人工 → complaint（转人工）；退款词 → complex"""
    t = text.strip().lower()
    # 纯问候 → simple（模糊问候 LLM 置信度低，避免被兜底成 complex 触发误审批）
    if t in GREETINGS or (len(t) <= 5 and any(g in t for g in GREETINGS)):
        return "simple"
    if any(k in text for k in HIGH_RISK_KEYWORDS):
        return "complaint"
    if any(k in text for k in HANDOVER_KEYWORDS):
        return "complaint"  # 用户主动要求转人工
    if any(k in text for k in REFUND_KEYWORDS):
        return "complex"
    return None


def handle_order_no_clarify(state: CustomerServiceState) -> dict:
    """澄清上下文：上一轮在等用户补充订单号，本条消息按澄清回答处理（不重新分类）"""
    last_user = state["messages"][-1].content

    # 高风险词/主动转人工优先：用户在澄清过程中表达投诉或要求人工 → 立即放弃澄清转人工
    # （投诉 100% 召回是红线，不能被澄清流程吞掉）
    if any(k in last_user for k in HIGH_RISK_KEYWORDS + HANDOVER_KEYWORDS):
        logger.info("澄清中命中高风险/转人工词，放弃澄清转人工", extra={"query": last_user[:30]})
        return {
            "intent": "complaint",
            "intent_confidence": 1.0,
            "risk_signals": ["complaint_during_clarify"],
            "pending_clarify": None,
            "clarify_count": 0,
        }

    order_no = extract_order_no(last_user)
    if order_no:
        logger.info("澄清成功：拿到订单号", extra={"order_no": order_no})
        return {
            "intent": "complex",
            "intent_confidence": 1.0,
            "risk_signals": ["clarified"],
            "order_no": order_no,
            "pending_clarify": None,
            "clarify_count": 0,
        }

    # 没识别到订单号 → 追问次数 +1，超限降级转人工（澄清防线①上限 + 降级链）
    count = (state.get("clarify_count") or 0) + 1
    if count >= MAX_CLARIFY:
        logger.warning(
            "澄清次数超限，降级转人工",
            extra={"clarify_count": count, "query": last_user[:30]},
        )
        return {
            "intent": "complaint",
            "intent_confidence": 0.0,
            "risk_signals": ["clarify_overflow"],
            "pending_clarify": None,
            "clarify_count": 0,
        }

    logger.info("未识别到订单号，继续追问", extra={"clarify_count": count, "query": last_user[:30]})
    return {"intent": "ask_order_no", "clarify_count": count}


def router_node(state: CustomerServiceState) -> dict:
    """分流节点：澄清上下文优先 → 三层分流（规则 → LLM 分类 → 置信度兜底）"""
    last_user = state["messages"][-1].content

    # 第0层：有未完成的澄清 → 本条消息按澄清回答处理（迭代3）
    if state.get("pending_clarify") == "order_no":
        return handle_order_no_clarify(state)

    # 第1层：规则快筛
    rule_result = rule_triage(last_user)
    if rule_result:
        logger.info(
            "分流结果",
            extra={"intent": rule_result, "source": "rule", "query": last_user[:30]},
        )
        intent, confidence, signals = rule_result, 1.0, [rule_result]
    else:
        # 第2层：LLM 分类（小模型 + 结构化输出）
        try:
            result = router_llm.invoke(
                [SystemMessage(content=ROUTER_PROMPT), ("user", last_user)]
            )
        except Exception as e:
            # 分类失败 → 兜底走复杂流程（稳妥，宁可错杀不可放过）
            logger.warning("分流失败，兜底走 complex", extra={"error": type(e).__name__})
            intent, confidence, signals = "complex", 0.0, []
        else:
            # 第3层：置信度兜底
            if result.intent == "complaint":
                intent = "complaint"
            elif result.confidence < 0.7:
                intent = "complex"  # 低置信 → 复杂流程
            else:
                intent = result.intent
            confidence, signals = result.confidence, result.risk_signals
            logger.info(
                "分流结果",
                extra={
                    "intent": intent,
                    "confidence": confidence,
                    "source": "llm",
                    "signals": signals,
                    "query": last_user[:30],
                },
            )

    updates = {"intent": intent, "intent_confidence": confidence, "risk_signals": signals}

    # 复杂售后：锁定订单号（优先级：最后一条消息 > state 已有）。
    # ⚠️ 不扫历史消息：旧案件的订单号会永久留在历史里，扫历史会导致新案件
    # 静默继承旧订单号（张冠李戴核实错订单）。state.order_no 也只在一个案件
    # 内有效——案件完结时由 approval 节点清空，新案件重新追问。
    if intent == "complex":
        candidate = extract_order_no(last_user) or state.get("order_no")
        if candidate and candidate != state.get("order_no"):
            logger.info("锁定订单号", extra={"order_no": candidate})
            updates["order_no"] = candidate

    return updates
