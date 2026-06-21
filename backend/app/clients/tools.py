from langchain_core.tools import BaseTool

from app.clients.brand_kit import (
    create_org_brand_kit,
    get_brand_voice_summary,
    import_brand_document,
    list_org_brand_kits,
    review_content_against_brand,
)
from app.clients.content_workflow import (
    get_phase_artifact_content,
    save_phase_artifact,
    scan_content_project_status,
)
from app.clients.marketing_research import search_market_research
from app.clients.pages_api import (
    create_page,
    create_page_version,
    delete_page,
    duplicate_page,
    get_insert_options,
    get_page_state,
    rename_page,
    search_pages,
    update_page_fields,
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
        search_market_research,
        list_org_brand_kits,
        get_brand_voice_summary,
        create_org_brand_kit,
        import_brand_document,
        review_content_against_brand,
        search_pages,
        get_insert_options,
        create_page,
        get_page_state,
        rename_page,
        duplicate_page,
        update_page_fields,
        create_page_version,
        delete_page,
    ]
