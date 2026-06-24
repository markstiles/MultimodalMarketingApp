import logging
import os

import httpx

from app.services._api_endpoint import api_endpoint

logger = logging.getLogger(__name__)

_BASE_URL = "https://edge-platform.sitecorecloud.io/stream/ai-pipeline-api"


def _get_base_url() -> str:
    return os.environ.get("SITECORE_PIPELINE_API_BASE_URL", _BASE_URL).rstrip("/")


def _auth_headers(auth_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


def _parse_pipeline_response(data: dict) -> dict:
    return {
        "success": True,
        "id": data.get("id", ""),
        "pipeline_id": data.get("pipelineId", ""),
        "status": data.get("status", ""),
        "message": data.get("message", ""),
        "created_on": data.get("createdOn", ""),
        "run_start": data.get("runStart", ""),
        "run_end": data.get("runEnd", ""),
        "duration_ms": data.get("durationInMs", 0),
    }


@api_endpoint(exposed=True, category="pipeline")
async def run_brand_ingestion_pipeline(
    org_id: str,
    brand_kit_id: str,
    auth_token: str,
    populate_sections: bool = True,
    document_ids_list: str = "",
) -> dict:
    """Run the brand ingestion pipeline for an organization's brand kit.

    POST /api/data/v1/organizations/{organizationId}/pipeline/BrandIngestionPipeline

    Analyzes documents uploaded to the brand kit, extracts brand information,
    and stores it as brand knowledge (knowledge chunks).

    Args:
        org_id:            Organization ID (e.g. "org_ABCDef123456")
        brand_kit_id:      UUID of the brand kit to ingest documents from
        populate_sections: Whether to auto-populate brand kit sections with
                           the ingested knowledge (default True)
        document_ids_list: Comma-separated document UUIDs to process; if empty,
                           all unprocessed documents in the brand kit are ingested

    Returns {success, id, pipeline_id, status, ...} on success or {success, error}.
    """
    url = f"{_get_base_url()}/api/data/v1/organizations/{org_id}/pipeline/BrandIngestionPipeline"
    parameters: dict = {
        "brand_kit_id": brand_kit_id,
        "populateSections": populate_sections,
    }
    if document_ids_list:
        parameters["documentIdsList"] = document_ids_list
    body = {"parameters": parameters}
    try:
        async with httpx.AsyncClient(timeout=60) as http:
            resp = await http.post(url, json=body, headers=_auth_headers(auth_token))
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPStatusError as exc:
        logger.error(
            "run_brand_ingestion_pipeline HTTP %d (org=%s, brand_kit=%s): %s",
            exc.response.status_code, org_id, brand_kit_id, exc.response.text,
        )
        return {"success": False, "error": f"HTTP {exc.response.status_code}: {exc.response.text[:300]}"}
    except Exception as exc:
        logger.error("run_brand_ingestion_pipeline error: %s", exc)
        return {"success": False, "error": str(exc)}

    return _parse_pipeline_response(data)


@api_endpoint(exposed=True, category="pipeline")
async def run_enrich_sections_pipeline(
    org_id: str,
    brand_kit_id: str,
    auth_token: str,
    section_id: str = "",
    field_id: str = "",
) -> dict:
    """Run the enrichment pipeline for a brand kit's sections.

    POST /api/data/v1/organizations/{organizationId}/pipeline/EnrichSectionsPipeline

    Uses existing brand knowledge to automatically populate or update content
    in brand kit sections and subsections.  Brand documents do NOT need to be
    re-ingested before calling this endpoint.

    Args:
        org_id:       Organization ID (e.g. "org_ABCDef123456")
        brand_kit_id: UUID of the brand kit to enrich
        section_id:   UUID of a specific section to enrich; if omitted, all
                      unlocked sections are enriched
        field_id:     UUID of a specific subsection to enrich; requires section_id
                      to also be provided; if omitted, all unlocked subsections
                      in the specified section are enriched

    Returns {success, id, pipeline_id, status, ...} on success or {success, error}.
    """
    url = f"{_get_base_url()}/api/data/v1/organizations/{org_id}/pipeline/EnrichSectionsPipeline"
    parameters: dict = {"brand_kit_id": brand_kit_id}
    if section_id:
        parameters["sectionId"] = section_id
    if field_id:
        parameters["fieldId"] = field_id
    body = {"parameters": parameters}
    try:
        async with httpx.AsyncClient(timeout=60) as http:
            resp = await http.post(url, json=body, headers=_auth_headers(auth_token))
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPStatusError as exc:
        logger.error(
            "run_enrich_sections_pipeline HTTP %d (org=%s, brand_kit=%s): %s",
            exc.response.status_code, org_id, brand_kit_id, exc.response.text,
        )
        return {"success": False, "error": f"HTTP {exc.response.status_code}: {exc.response.text[:300]}"}
    except Exception as exc:
        logger.error("run_enrich_sections_pipeline error: %s", exc)
        return {"success": False, "error": str(exc)}

    return _parse_pipeline_response(data)
