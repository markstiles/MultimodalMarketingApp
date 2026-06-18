import os

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.resources.schemas import AuthStatus, UserRead

router = APIRouter()


@router.get("/auth/status")
async def auth_status(request: Request) -> JSONResponse:
    runtime_context = os.environ.get("RUNTIME_CONTEXT", "iframe")

    if runtime_context == "local":
        return JSONResponse(
            {
                "authenticated": True,
                "user": {"id": "local-user", "email": "dev@local"},
                "expiresAt": None,
            }
        )

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return JSONResponse({"authenticated": False, "user": None, "expiresAt": None})

    return JSONResponse({"authenticated": True, "user": None, "expiresAt": None})
