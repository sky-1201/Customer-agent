"""结构化输出模型（技术诊断 / 售后核实 / 最终决策）"""
from typing import Literal, Optional

from pydantic import BaseModel, Field


class TechResult(BaseModel):
    """技术诊断结果（技术诊断节点输出）"""

    fault: str = Field(description="故障现象，如'蓝屏死机'")
    same_fault: bool = Field(description="多次维修是否属于同一故障（'修两次'场景的关键）")
    cause: str = Field(description="可能的故障原因")
    confidence: float = Field(ge=0, le=1, description="置信度")


class AftersaleResult(BaseModel):
    """售后核实结果（售后核实节点输出）"""

    order_no: Optional[str] = Field(default=None, description="订单号（节点从数据库精确覆盖）")
    purchase_date: Optional[str] = Field(default=None, description="购买时间（节点从数据库精确覆盖）")
    order_valid: bool = Field(description="订单是否有效存在")
    in_warranty: bool = Field(description="是否在三包期内")
    repair_count: int = Field(description="维修次数")
    policy_applicable: bool = Field(description="政策是否适用（能否换货/退货）")
    policy_ref: str = Field(description="政策条款引用（来自结构化查询，非 LLM 编造）")
    confidence: float = Field(ge=0, le=1, description="置信度")


class FinalDecision(BaseModel):
    """最终决策（决策节点交叉核验后输出）"""

    conclusion: Literal["换货", "退货", "维修", "不满足", "转人工"] = Field(description="结论")
    confidence: float = Field(ge=0, le=1, description="置信度")
    reasoning: str = Field(description="交叉核验的推理过程")
    policy_ref: str = Field(description="政策依据（可溯源）")
    comfort_msg: str = Field(description="安抚话术（回复给用户）")
