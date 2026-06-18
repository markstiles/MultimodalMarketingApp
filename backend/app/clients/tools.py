from langchain_core.tools import BaseTool

_mcp_tools: list[BaseTool] = []


def set_mcp_tools(tools: list[BaseTool]) -> None:
    global _mcp_tools
    _mcp_tools = tools


def get_all_tools() -> list[BaseTool]:
    return _mcp_tools
