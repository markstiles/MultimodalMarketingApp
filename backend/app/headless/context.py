"""Proxy context for headless operation.

Replaces the Sitecore iframe context that the browser normally supplies.
All values come from environment variables; HEADLESS_* vars take priority,
with LOCAL_* vars as fallback (they already exist in every local .env).
"""
import os
from dataclasses import dataclass


@dataclass
class ProxyContext:
    site_id: str
    page_id: str
    language: str
    user_id: str
    user_name: str | None = None
    user_email: str | None = None

    def to_runtime_context(self):
        from app.resources.schemas import RuntimeContext

        return RuntimeContext(
            site_id=self.site_id,
            page_id=self.page_id,
            language=self.language,
            user_name=self.user_name,
            user_email=self.user_email,
        )

    def summary(self) -> str:
        parts = [f"site={self.site_id}", f"page={self.page_id}", f"lang={self.language}"]
        if self.user_name:
            parts.append(f"user={self.user_name}")
        return ", ".join(parts)


def load_proxy_context() -> ProxyContext:
    """Load ProxyContext from environment variables.

    Required env vars (with defaults):
        HEADLESS_SITE_ID     — falls back to LOCAL_SITE_ID or "stub-site-id"
        HEADLESS_PAGE_ID     — falls back to LOCAL_PAGE_ID or "stub-page-id"
        HEADLESS_LANGUAGE    — falls back to LOCAL_LANGUAGE or "en"

    Optional env vars:
        HEADLESS_USER_ID     — default "headless-runner"
        HEADLESS_USER_NAME   — displayed in session context
        HEADLESS_USER_EMAIL  — displayed in session context
    """
    return ProxyContext(
        site_id=(
            os.environ.get("HEADLESS_SITE_ID")
            or os.environ.get("LOCAL_SITE_ID", "stub-site-id")
        ),
        page_id=(
            os.environ.get("HEADLESS_PAGE_ID")
            or os.environ.get("LOCAL_PAGE_ID", "stub-page-id")
        ),
        language=(
            os.environ.get("HEADLESS_LANGUAGE")
            or os.environ.get("LOCAL_LANGUAGE", "en")
        ),
        user_id=os.environ.get("HEADLESS_USER_ID", "headless-runner"),
        user_name=os.environ.get("HEADLESS_USER_NAME"),
        user_email=os.environ.get("HEADLESS_USER_EMAIL"),
    )
