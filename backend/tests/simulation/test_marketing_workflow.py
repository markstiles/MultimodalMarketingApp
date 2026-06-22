"""Simulation tests for the AI marketing pipeline.

Each test runs one SimScenario through the full headless pipeline stack and
asserts that the expected tools were called and the scenario completed.

These tests require a live Sitecore environment — see conftest.py for the full
list of required env vars.  They are skipped automatically in CI unless those
vars are present.

Run all simulation tests:
    pytest tests/simulation/ -m simulation -v

Run a specific scenario:
    pytest tests/simulation/ -m simulation -k "research-full" -v

Or via the CLI runner for interactive verbose output:
    python -m scripts.headless_run --scenario research-full --verbose
"""
import pytest

from tests.simulation.conftest import assert_scenario_passed, skip_without_sitecore
from tests.simulation.scenarios import (
    S01_SESSION_START,
    S02_RESEARCH_FULL,
    S03_BRIEF_ENTRY,
    S04_BRAND_VOICE_EXISTING_KIT,
    S05_STRATEGY,
    S06_CAMPAIGN_PERSONALIZATION,
    S07_LANGUAGE_MANAGEMENT,
    S08_OVERWRITE_EXISTING,
    S09_CREATE_TEST_SITE,
    S10_CAMPAIGN_PAGE_STRUCTURE,
    S11_POPULATE_PAGE_CONTENT,
    S12_FULL_MICROSITE_SETUP,
    S13_AB_TEST_VARIANT,
    S14_IMAGE_SEARCH_FIND_SELECT,
    S15_IMAGE_SEARCH_POPULATE_COMPONENT,
)

pytestmark = [pytest.mark.simulation, pytest.mark.asyncio, skip_without_sitecore]


# ─── S01: Session start ───────────────────────────────────────────────────────


async def test_session_start_scans_pipeline_status(run_scenario):
    """Assistant must open with a pipeline status scan before helping."""
    result = await run_scenario(S01_SESSION_START)
    assert_scenario_passed(result, S01_SESSION_START)
    assert result.total_turns <= 5, (
        f"Status scan should resolve in ≤5 turns, took {result.total_turns}"
    )


# ─── S02: Research phase ──────────────────────────────────────────────────────


async def test_research_phase_runs_web_search_and_saves_brief(run_scenario):
    """Full research flow: scan → web search → draft → approve → save."""
    result = await run_scenario(S02_RESEARCH_FULL)
    assert_scenario_passed(result, S02_RESEARCH_FULL)

    tools = {t for r in result.turns for t in r.tool_calls}
    assert "search_market_research" in tools, (
        "Research phase must call search_market_research; "
        f"tools called: {sorted(tools)}"
    )


# ─── S03: Brief entry point ───────────────────────────────────────────────────


async def test_brief_entry_skips_earlier_phases(run_scenario):
    """Existing brief path: marketer pastes brief, assistant saves it directly."""
    result = await run_scenario(S03_BRIEF_ENTRY)
    assert_scenario_passed(result, S03_BRIEF_ENTRY)

    tools = {t for r in result.turns for t in r.tool_calls}
    # Should NOT have needed web research for an existing brief
    assert "search_market_research" not in tools, (
        "Brief entry point should not trigger web research; "
        f"tools called: {sorted(tools)}"
    )


# ─── S04: Brand voice ─────────────────────────────────────────────────────────


async def test_brand_voice_phase_uses_existing_kit(run_scenario):
    """Brand voice flow: list brand kits → select → get summary → save."""
    result = await run_scenario(S04_BRAND_VOICE_EXISTING_KIT)
    assert_scenario_passed(result, S04_BRAND_VOICE_EXISTING_KIT)


# ─── S05: Strategy ───────────────────────────────────────────────────────────


async def test_strategy_phase_saves_marketing_strategy(run_scenario):
    """Strategy flow: scan → (optionally read Research) → ask questions → save."""
    result = await run_scenario(S05_STRATEGY)
    assert_scenario_passed(result, S05_STRATEGY)

    tools = {t for r in result.turns for t in r.tool_calls}
    assert "save_phase_artifact" in tools, (
        f"Strategy phase must save an artifact; tools called: {sorted(tools)}"
    )


# ─── S06: Campaign tactics ────────────────────────────────────────────────────


async def test_campaign_phase_personalization_tactic(run_scenario):
    """Campaign flow: scan → read Brief → personalization tactic → save."""
    result = await run_scenario(S06_CAMPAIGN_PERSONALIZATION)
    assert_scenario_passed(result, S06_CAMPAIGN_PERSONALIZATION)


# ─── S07: Language management ─────────────────────────────────────────────────


async def test_site_language_management_lists_and_adds(run_scenario):
    """Language flow: get site context → list languages → add fr-CA if absent."""
    result = await run_scenario(S07_LANGUAGE_MANAGEMENT)
    assert_scenario_passed(result, S07_LANGUAGE_MANAGEMENT)

    tools = {t for r in result.turns for t in r.tool_calls}
    assert "list_site_languages" in tools, (
        f"Language scenario must call list_site_languages; tools: {sorted(tools)}"
    )


# ─── S08: Overwrite existing artifact ────────────────────────────────────────


async def test_overwrite_existing_research_brief(run_scenario):
    """Refresh flow: existing Research Brief is overwritten without blocking."""
    result = await run_scenario(S08_OVERWRITE_EXISTING)
    assert_scenario_passed(result, S08_OVERWRITE_EXISTING)

    tools = {t for r in result.turns for t in r.tool_calls}
    assert "search_market_research" in tools, (
        "Overwrite scenario must run fresh web research; "
        f"tools called: {sorted(tools)}"
    )
    assert "save_phase_artifact" in tools, (
        "Overwrite scenario must re-save the artifact; "
        f"tools called: {sorted(tools)}"
    )


# ─── S09: Create test collection + site ──────────────────────────────────────


async def test_create_test_collection_and_site(run_scenario):
    """Site provisioning: list existing → confirm name/collection → create site."""
    result = await run_scenario(S09_CREATE_TEST_SITE)
    assert_scenario_passed(result, S09_CREATE_TEST_SITE)

    tools = {t for r in result.turns for t in r.tool_calls}
    assert "list_all_sites" in tools, (
        "Must check existing sites before creating; "
        f"tools called: {sorted(tools)}"
    )
    assert "create_marketing_site" in tools, (
        "Must call create_marketing_site; "
        f"tools called: {sorted(tools)}"
    )


# ─── S10: Campaign page structure ─────────────────────────────────────────────


async def test_campaign_page_structure_creates_three_pages(run_scenario):
    """Page setup: discover templates → create 3 pages with marketer approval."""
    result = await run_scenario(S10_CAMPAIGN_PAGE_STRUCTURE)
    assert_scenario_passed(result, S10_CAMPAIGN_PAGE_STRUCTURE)

    # Count how many times create_page was called — should be ≥3
    create_page_calls = sum(
        r.tool_calls.count("create_page") for r in result.turns
    )
    assert create_page_calls >= 3, (
        f"Expected at least 3 create_page calls for 3 pages, got {create_page_calls}; "
        f"all tools: {sorted({t for r in result.turns for t in r.tool_calls})}"
    )


# ─── S11: Populate page content from brief ───────────────────────────────────


async def test_populate_page_content_from_brief(run_scenario):
    """Content population: read brief → derive field values → update page fields."""
    result = await run_scenario(S11_POPULATE_PAGE_CONTENT)
    assert_scenario_passed(result, S11_POPULATE_PAGE_CONTENT)

    tools = {t for r in result.turns for t in r.tool_calls}
    assert "get_phase_artifact_content" in tools, (
        "Must read campaign brief before populating page content; "
        f"tools called: {sorted(tools)}"
    )
    assert "update_page_fields" in tools, (
        "Must call update_page_fields to set content; "
        f"tools called: {sorted(tools)}"
    )


# ─── S12: Full microsite setup ────────────────────────────────────────────────


async def test_full_microsite_setup_end_to_end(run_scenario):
    """Integration smoke test: brief → site → pages → content in one conversation."""
    result = await run_scenario(S12_FULL_MICROSITE_SETUP)
    assert_scenario_passed(result, S12_FULL_MICROSITE_SETUP)

    tools = {t for r in result.turns for t in r.tool_calls}
    # All four phases of the microsite workflow must be represented
    assert "create_marketing_site" in tools, f"Missing create_marketing_site; tools: {sorted(tools)}"
    assert "create_page" in tools, f"Missing create_page; tools: {sorted(tools)}"
    assert "get_phase_artifact_content" in tools, f"Missing get_phase_artifact_content; tools: {sorted(tools)}"
    assert "update_page_fields" in tools, f"Missing update_page_fields; tools: {sorted(tools)}"


# ─── S13: A/B test variant ────────────────────────────────────────────────────


async def test_ab_test_variant_duplicates_and_updates(run_scenario):
    """A/B variant: find page → duplicate → update variant fields with alt copy."""
    result = await run_scenario(S13_AB_TEST_VARIANT)
    assert_scenario_passed(result, S13_AB_TEST_VARIANT)

    tools = {t for r in result.turns for t in r.tool_calls}
    assert "duplicate_page" in tools, (
        "A/B variant must duplicate the source page; "
        f"tools called: {sorted(tools)}"
    )
    assert "update_page_fields" in tools, (
        "A/B variant must update fields on the duplicated page; "
        f"tools called: {sorted(tools)}"
    )


# ─── S14: Image search — find and select ─────────────────────────────────────


async def test_image_search_finds_results_for_description(run_scenario):
    """Image search: query by description → receive ranked results with media paths."""
    result = await run_scenario(S14_IMAGE_SEARCH_FIND_SELECT)
    assert_scenario_passed(result, S14_IMAGE_SEARCH_FIND_SELECT)

    tools = {t for r in result.turns for t in r.tool_calls}
    assert "search_site_images" in tools, (
        "Image search scenario must call search_site_images; "
        f"tools called: {sorted(tools)}"
    )


# ─── S15: Image search — find and populate component ─────────────────────────


async def test_image_search_places_selected_image_on_page(run_scenario):
    """Image search → placement: query → pick result → set media_path on page field."""
    result = await run_scenario(S15_IMAGE_SEARCH_POPULATE_COMPONENT)
    assert_scenario_passed(result, S15_IMAGE_SEARCH_POPULATE_COMPONENT)

    tools = {t for r in result.turns for t in r.tool_calls}
    assert "search_site_images" in tools, (
        "Must call search_site_images to find the image; "
        f"tools called: {sorted(tools)}"
    )
    assert "update_page_fields" in tools, (
        "Must call update_page_fields to place the image on the page; "
        f"tools called: {sorted(tools)}"
    )
