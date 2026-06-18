"""Copy NEXT_PUBLIC_* and API_URL vars from root .env → frontend/.env.local."""
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
SRC = ROOT / ".env"
DEST = ROOT / "frontend" / ".env.local"

if not SRC.exists():
    print("No .env at project root — skipping frontend env generation")
    raise SystemExit(0)

# Only copy vars the frontend actually references — backend vars stay backend-only.
FRONTEND_VARS = {
    "API_URL",
    "RUNTIME_CONTEXT",
    "LOCAL_USER_ID",
    "AUTH0_BASE_URL",
    "AUTH0_CLIENT_ID",
    "AUTH0_CLIENT_SECRET",
    "AUTH0_ISSUER_BASE_URL",
    "NEXT_PUBLIC_RUNTIME_CONTEXT",
    "NEXT_PUBLIC_LOCAL_PAGE_ID",
    "NEXT_PUBLIC_LOCAL_SITE_ID",
    "NEXT_PUBLIC_LOCAL_LANGUAGE",
}

lines = [
    line for line in SRC.read_text(encoding="utf-8").splitlines()
    if line.split("=")[0].strip() in FRONTEND_VARS
]

DEST.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"Generated frontend/.env.local ({len(lines)} var(s))")
