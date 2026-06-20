import os
import time
from typing import Any

import httpx

_token_cache: dict[str, Any] = {}


async def get_sitecore_automation_token() -> str:
    """Acquire (or return cached) a Bearer token for the Sitecore automation client.

    Uses the client_credentials grant against Auth0. The token is cached in memory
    and refreshed 60 seconds before its reported expiry. Raises RuntimeError when
    the required env vars are absent.
    """
    now = time.monotonic()
    if _token_cache.get("expires_at", 0) > now + 60:
        return _token_cache["token"]

    client_id = (
        os.environ.get("SITECORE_CLIENT_ID_AUTOMATION")
        or os.environ.get("AUTHOR_APP_ID", "")
    )
    client_secret = (
        os.environ.get("SITECORE_CLIENT_SECRET_AUTOMATION")
        or os.environ.get("AUTHOR_APP_CLIENT_CREDENTIALS", "")
    )
    if not client_id or not client_secret:
        raise RuntimeError(
            "Sitecore automation credentials missing — set SITECORE_CLIENT_ID_AUTOMATION "
            "and SITECORE_CLIENT_SECRET_AUTOMATION in your .env"
        )

    token_url = os.environ.get(
        "SITECORE_AUTH_TOKEN_URL",
        "https://auth.sitecorecloud.io/oauth/token",
    )
    audience = os.environ.get(
        "SITECORE_AUTH_AUDIENCE",
        "https://api.sitecorecloud.io",
    )

    async with httpx.AsyncClient(timeout=10) as http:
        resp = await http.post(
            token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
                "audience": audience,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        data = resp.json()

    _token_cache["token"] = data["access_token"]
    _token_cache["expires_at"] = now + data.get("expires_in", 3600)
    return _token_cache["token"]
