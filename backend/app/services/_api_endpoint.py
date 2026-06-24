"""
API endpoint accessibility annotations for service-layer functions.

Usage
-----
Apply @api_endpoint to every async service function to declare whether it is
appropriate to surface as a direct @tool wrapper, or whether it should only be
called from a composite tool that provides additional context, validation, or
safety checks.

    @api_endpoint(exposed=True, category="pages")
    async def search_pages_api(...):
        ...

    @api_endpoint(exposed=False, category="pages")
    async def delete_page_api(...):
        ...

Tiers
-----
exposed=True   — safe to wrap as a thin @tool; the LLM has all the information
                 it needs to call this function directly.

exposed=False  — building-block only; the function is either:
                   • destructive (delete / cancel) and needs a confirming wrapper
                   • requires prior context that the LLM cannot supply on its own
                     (e.g. template_id must come from a prior insert-options call)
                   • a pure internal utility (lookup, cache, fallback)

This is documentation-only — nothing enforces the constraint at runtime.

Client-layer tools
------------------
After a @tool is defined in app/clients/*.py, set its ._tier attribute to one of
the constants below so the client module is self-documenting:

    TOOL_TIER_DIRECT    = "direct"      # thin wrapper around an exposed=True service
    TOOL_TIER_COMPOSITE = "composite"   # calls ≥1 exposed=False service internally
"""

from dataclasses import dataclass
from typing import Callable, TypeVar

# ── tier constants used by client/@tool files ─────────────────────────────────

TOOL_TIER_DIRECT = "direct"
TOOL_TIER_COMPOSITE = "composite"


# ── decorator ─────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ApiEndpointMeta:
    exposed: bool
    category: str = ""


F = TypeVar("F", bound=Callable)


def api_endpoint(*, exposed: bool, category: str = "") -> Callable[[F], F]:
    """Attach accessibility metadata to a service-layer async function."""
    def decorator(fn: F) -> F:
        fn._api_endpoint = ApiEndpointMeta(exposed=exposed, category=category)
        return fn
    return decorator
