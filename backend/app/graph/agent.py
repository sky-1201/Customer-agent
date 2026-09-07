"""客服 Agent（simple 分支：ReAct 循环 + 2 个检索工具，作为主图的子图）"""
from langchain_core.messages import SystemMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from app.config import AGENT_MODEL, DASHSCOPE_API_KEY, DASHSCOPE_BASE_URL
from app.graph.state import CustomerServiceState
from app.kb.search import search_faq, search_troubleshooting
from app.utils.logger import get_logger

logger = get_logger("customer_agent")

SYSTEM_PROMPT = """你是笔记本电商的智能客服，负责回答用户的咨询。

你可以使用 search_faq 工具查询常见问题，使用 search_troubleshooting 工具查询故障原因和排查方法。

要求：
- 回答简洁友好，用中文
- 知识库查不到时，如实告知并建议联系人工客服
- 不要编造不存在的信息
"""


@tool
def search_faq_tool(query: str) -> str:
    """检索 FAQ 知识库，回答常见问题（售后政策、使用方法、物流、保修等）。"""
    return search_faq(query)


@tool
def search_troubleshooting_tool(query: str) -> str:
    """检索故障说明知识库，查询电脑故障的原因和排查方法（如蓝屏、开不了机等）。"""
    return search_troubleshooting(query)


tools = [search_faq_tool, search_troubleshooting_tool]

llm = ChatOpenAI(
    api_key=DASHSCOPE_API_KEY,
    base_url=DASHSCOPE_BASE_URL,
    model=AGENT_MODEL,
    temperature=0.3,
).bind_tools(tools)


def agent_node(state: CustomerServiceState):
    """LLM 推理节点：产出回复或工具调用"""
    response = llm.invoke([SystemMessage(content=SYSTEM_PROMPT)] + state["messages"])
    return {"messages": [response]}


def should_continue(state: CustomerServiceState) -> str:
    """条件边：有 tool_calls 就去执行工具，否则结束"""
    last = state["messages"][-1]
    if getattr(last, "tool_calls", None):
        names = [tc["name"] for tc in last.tool_calls]
        logger.info("Agent 调用工具", extra={"tools": names})
        return "tools"
    return END


builder = StateGraph(CustomerServiceState)
builder.add_node("agent", agent_node)
builder.add_node("tools", ToolNode(tools))
builder.add_edge(START, "agent")
builder.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
builder.add_edge("tools", "agent")

# 客服 Agent 作为子图（不带 checkpoint，由主图统一管理）
agent_graph = builder.compile()
