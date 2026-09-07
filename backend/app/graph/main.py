"""主图：router → 条件分支（simple / complex / complaint）

complex 分支：并行[技术诊断 ∥ 售后核实] → 决策交叉核验 → 审批/回复
"""
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send
from psycopg_pool import AsyncConnectionPool, ConnectionPool

from app.config import DATABASE_URL
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

# checkpoint 持久化到 PostgreSQL：
# - 审批等待中服务重启，状态不丢（从 checkpoint 恢复继续等审批）
# - 时间旅行：可回到任意历史状态排查
# 用连接池（from_conn_string 是短连接 context manager，不适合模块级常驻 checkpointer）
PG_CONN_STRING = DATABASE_URL.replace("+psycopg", "")  # 转 psycopg 原生连接字符串

# 1. setup 用同步 autocommit 临时池：migration 含 CREATE INDEX CONCURRENTLY，不能在事务块里执行
_setup_pool = ConnectionPool(conninfo=PG_CONN_STRING, kwargs={"autocommit": True})
PostgresSaver(_setup_pool).setup()  # 建 checkpoint 表（幂等）
_setup_pool.close()

# 2. checkpointer 用异步池（ainvoke/astream 需要 AsyncPostgresSaver，同步版不支持异步方法）
checkpoint_pool = AsyncConnectionPool(conninfo=PG_CONN_STRING, open=False)  # lifespan 里 open
checkpointer = AsyncPostgresSaver(checkpoint_pool)

main_graph = builder.compile(checkpointer=checkpointer)
