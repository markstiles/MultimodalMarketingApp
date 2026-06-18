import logging

from langchain_core.messages import BaseMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode

logger = logging.getLogger(__name__)

_chat_graph = None


def _build_graph(tools):
    from app.clients.llm import get_llm

    llm = get_llm().bind_tools(tools) if tools else get_llm()
    tool_node = ToolNode(tools, handle_tool_errors=True)

    async def _model_node(state: MessagesState, config: RunnableConfig) -> dict:
        full = None
        async for chunk in llm.astream(state["messages"], config):
            full = chunk if full is None else full + chunk
        return {"messages": [full]}

    def _should_continue(state: MessagesState) -> str:
        last: BaseMessage = state["messages"][-1]
        if hasattr(last, "tool_calls") and last.tool_calls:
            return "tools"
        return END

    builder = StateGraph(MessagesState)
    builder.add_node("model", _model_node)
    builder.add_node("tools", tool_node)
    builder.set_entry_point("model")
    builder.add_conditional_edges("model", _should_continue, {"tools": "tools", END: END})
    builder.add_edge("tools", "model")
    return builder.compile()


def build_chat_graph() -> None:
    """Build (or rebuild) the graph with the currently registered tools."""
    global _chat_graph
    from app.clients.tools import get_all_tools

    tools = get_all_tools()
    logger.info("Building chat graph with %d tools: %s", len(tools), [t.name for t in tools])
    _chat_graph = _build_graph(tools)


def get_chat_graph():
    global _chat_graph
    if _chat_graph is None:
        build_chat_graph()
    return _chat_graph
