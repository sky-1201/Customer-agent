"""统一状态定义（主图与各子图共用）"""
from typing import Annotated, Optional, TypedDict

from langgraph.graph.message import add_messages

from app.models.structured import AftersaleResult, FinalDecision, TechResult


class CustomerServiceState(TypedDict):
    # 对话历史（add_messages reducer：追加而非覆盖）
    messages: Annotated[list, add_messages]
    # 会话标识（审批 resume 时用，由 chat 接口传入）
    thread_id: Optional[str]
    # 分流结果（router 节点写入）
    intent: Optional[str]              # simple / complex / complaint
    intent_confidence: Optional[float]
    risk_signals: Optional[list[str]]
    # 复杂售后并行结果（各写各的字段，避免 reducer 冲突）
    tech_result: Optional[TechResult]          # 技术诊断
    aftersale_result: Optional[AftersaleResult]  # 售后核实
    final_decision: Optional[FinalDecision]      # 决策（交叉核验）
