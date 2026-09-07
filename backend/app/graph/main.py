"""主图：router → 条件分支（simple / complex / complaint）

complex 分支：并行[技术诊断 ∥ 售后核实] → 决策交叉核验 → 审批/回复
"""
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from app.graph.aftersale import aftersale_node
from app.graph.agent import agent_graph
from app.graph.approval import approval_node
from app.graph.decision import decision_node
from app.graph.router import router_node
from app.graph.state import CustomerServiceState
from app.graph.tech import tech_node
from app.utils.logger import get_logger

logger = get_logger("main_graph")


def complaint_placeholder(state: CustomerServiceState) -> dict:
    """投诉占位（阶段4实现转人工）"""
    return {"messages": [("assistant", "（投诉转人工将后续实现，请稍后）")]}


def route(state: CustomerServiceState):
    """条件边：根据 intent 路由。complex 返回 Send 列表做并行 fan-out。"""
    intent = state.get("intent", "simple")

    if intent == "complex":
        logger.info("复杂售后并行分发", extra={"targets": ["tech", "aftersale"]})
        # Send 的第二个参数是目标节点接收的 state，需传完整 state（否则拿不到 messages）
        return [Send("tech", state), Send("aftersale", state)]

    if intent == "complaint":
        return "complaint_placeholder"

    return "customer_agent"


builder = StateGraph(CustomerServiceState)
builder.add_node("router", router_node)
builder.add_node("customer_agent", agent_graph)          # 子图（simple 分支）
builder.add_node("tech", tech_node)                      # 技术诊断（complex 并行一路）
builder.add_node("aftersale", aftersale_node)            # 售后核实（complex 并行一路）
builder.add_node("decision", decision_node)              # 交叉核验
builder.add_node("approval", approval_node)              # 审批/回复
builder.add_node("complaint_placeholder", complaint_placeholder)

builder.add_edge(START, "router")
builder.add_conditional_edges(
    "router",
    route,
    ["customer_agent", "tech", "aftersale", "complaint_placeholder"],
)

# simple / complaint 分支直达 END
builder.add_edge("customer_agent", END)
builder.add_edge("complaint_placeholder", END)

# complex 分支：tech 和 aftersale 都完成后汇聚到 decision → approval → END
builder.add_edge("tech", "decision")
builder.add_edge("aftersale", "decision")
builder.add_edge("decision", "approval")
builder.add_edge("approval", END)

main_graph = builder.compile(checkpointer=MemorySaver())
