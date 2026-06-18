import os
from typing import Optional

import httpx
from fastapi import HTTPException, Request


async def get_user_id(request: Request) -> str:
    """Return user_id from request. In local mode, reads X-Local-User-Id header."""
    runtime_context = os.environ.get("RUNTIME_CONTEXT", "iframe")

    if runtime_context == "local":
        user_id = request.headers.get("X-Local-User-Id", "local-user")
        return user_id

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="unauthorized")

    token = auth_header.removeprefix("Bearer ").strip()
    return await _verify_jwt(token)


async def _verify_jwt(token: str) -> str:
    """Validate JWT against Auth0 JWKS and return the sub claim as user_id."""
    try:
        import jwt as pyjwt  # python-jose or PyJWT depending on installed pkg

        # Fetch JWKS
        issuer = os.environ.get("AUTH0_ISSUER_BASE_URL", "")
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{issuer}/.well-known/jwks.json")
            resp.raise_for_status()
            jwks = resp.json()

        # Decode header to get kid
        header = pyjwt.get_unverified_header(token)
        key = _find_key(jwks["keys"], header.get("kid"))

        audience = os.environ.get("AUTH0_CLIENT_ID", "")
        payload = pyjwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=audience,
            issuer=issuer + "/",
        )
        return payload["sub"]
    except Exception:
        raise HTTPException(status_code=401, detail="unauthorized")


def _find_key(keys: list, kid: Optional[str]) -> dict:
    for k in keys:
        if k.get("kid") == kid:
            return k
    raise HTTPException(status_code=401, detail="unauthorized")
