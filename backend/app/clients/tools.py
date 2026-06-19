from langchain_core.tools import BaseTool

from app.clients.content_workflow import (
    get_phase_artifact_content,
    save_phase_artifact,
    scan_content_project_status,
)

_mcp_tools: list[BaseTool] = []


def set_mcp_tools(tools: list[BaseTool]) -> None:
    global _mcp_tools
    _mcp_tools = tools


def get_all_tools() -> list[BaseTool]:
    return [
        *_mcp_tools,
        scan_content_project_status,
        save_phase_artifact,
        get_phase_artifact_content,
    ]
