from langchain_core.tools import BaseTool

from app.clients.brief import (
    delete_campaign_brief,
    find_campaign_brief,
    generate_campaign_brief,
    get_brief_types,
    get_campaign_brief,
    save_campaign_brief,
    update_campaign_brief,
)
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
from app.clients.sites import (
    add_language_to_site,
    create_marketing_site,
    create_site_collection,
    delete_marketing_site,
    get_environment_languages,
    get_site_context,
    get_site_templates,
    list_all_sites,
    list_site_collections,
    list_site_languages,
    remove_language_from_site,
    validate_site_name,
)
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
from app.clients.image_search import (
    index_media_library_images,
    search_site_images,
)
from app.clients.ui_tools import present_options

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
        get_site_context,
        list_all_sites,
        list_site_collections,
        create_site_collection,
        get_site_templates,
        get_environment_languages,
        validate_site_name,
        create_marketing_site,
        delete_marketing_site,
        list_site_languages,
        add_language_to_site,
        remove_language_from_site,
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
        search_site_images,
        index_media_library_images,
        get_brief_types,
        generate_campaign_brief,
        save_campaign_brief,
        get_campaign_brief,
        update_campaign_brief,
        find_campaign_brief,
        delete_campaign_brief,
        present_options,
    ]
