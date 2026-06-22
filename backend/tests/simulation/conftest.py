"""Pytest configuration for headless simulation tests.

Simulation tests require a live Sitecore environment and are skipped
automatically when the required environment variables are not set.

To run simulation tests:
    pytest tests/simulation/ -m simulation -v

Required env vars:
    LLM_API_KEY, DATABASE_URL, HEADLESS_SITE_ID, HEADLESS_PAGE_ID,
    SITECORE_CM_HOST, SITECORE_AGENTS_API_BASE_URL,
    AUTHOR_APP_ID, AUTHOR_APP_CLIENT_CREDENTIALS
"""
import os

import pytest

from tests.simulation.scenarios import SimScenario

# ── Skip guard ────────────────────────────────────────────────────────────────

_REQUIRED_ENV_VARS = [
    "LLM_API_KEY",
    "DATABASE_URL",
    "HEADLESS_SITE_ID",
    "HEADLESS_PAGE_ID",
    "SITECORE_CM_HOST",
    "SITECORE_AGENTS_API_BASE_URL",
    "AUTHOR_APP_ID",
    "AUTHOR_APP_CLIENT_CREDENTIALS",
]


def _missing_vars() -> list[str]:
    return [v for v in _REQUIRED_ENV_VARS if not os.environ.get(v)]


_SKIP_REASON = (
    "Simulation tests require a live Sitecore environment. "
    "Set these env vars to enable: " + ", ".join(_REQUIRED_ENV_VARS)
)

skip_without_sitecore = pytest.mark.skipif(
    bool(_missing_vars()),
    reason=_SKIP_REASON + (
        f" (missing: {', '.join(_missing_vars())})" if _missing_vars() else ""
    ),
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def run_scenario():
    """Async fixture that runs a SimScenario and returns its RunResult."""
    from app.headless.runner import HeadlessRunner, RunResult

    async def _run(scenario: SimScenario, **overrides) -> RunResult:
        runner = HeadlessRunner(
            scenario=scenario.scenario_prompt,
            max_turns=overrides.get("max_turns", scenario.max_turns),
            files_source=overrides.get("files_source", scenario.files_source),
            verbose=overrides.get("verbose", False),
        )
        return await runner.run()

    return _run


# ── Assertion helpers ─────────────────────────────────────────────────────────


def all_tools_called(result) -> set[str]:
    """Return the set of all tool names called across all turns."""
    return {t for r in result.turns for t in r.tool_calls}


def assert_scenario_passed(result, scenario: SimScenario) -> None:
    """Assert that a RunResult meets the scenario's expectations."""
    tools_called = all_tools_called(result)

    missing = scenario.required_tools - tools_called
    assert not missing, (
        f"[{scenario.id}] Required tools not called: {missing}\n"
        f"Tools that were called: {sorted(tools_called)}"
    )

    assert result.completed, (
        f"[{scenario.id}] Driver did not signal completion "
        f"(ran {result.total_turns}/{scenario.max_turns} turns). "
        f"Tools called: {sorted(tools_called)}"
    )

    if scenario.saves_artifact:
        canvas_reloads = sum(1 for r in result.turns if r.canvas_reload)
        assert canvas_reloads >= 1, (
            f"[{scenario.id}] Expected a canvas_reload event (artifact save) "
            f"but none occurred across {result.total_turns} turns."
        )
