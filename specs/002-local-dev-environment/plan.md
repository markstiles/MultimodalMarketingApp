# Implementation Plan: Local Development Environment

**Branch**: `002-local-dev-environment` | **Date**: 2026-06-17 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/002-local-dev-environment/spec.md`

## Summary

Create a single-command local development environment that starts Docker-managed infrastructure (PostgreSQL, MLflow), validates configuration, runs database migrations, and launches the FastAPI backend and Next.js frontend as native processes with unified log output. The environment mirrors the deployed Railway topology — the backend is internal-only, accessible only via the Next.js proxy. Hot reload is enabled for both services.

## Technical Context

**Backend scripts**: Python 3.12 (same runtime as the backend)

**Frontend**: Next.js 15 (Node.js runtime, `next dev` for hot reload)

**Primary Dependencies** (new, for dev tooling only):
- `just` — task runner binary (single install, cross-platform)
- `honcho` — Procfile process manager; `pip install honcho` (Python, no new runtime)
- `tenacity` — retry library for DB readiness polling; `pip install tenacity`
- `docker compose` (V2) — infra-only: PostgreSQL + MLflow

**Storage**: N/A — no new database entities in this feature

**Testing**: Manual smoke tests per quickstart.md validation scenarios

**Target Platform**: Windows 11 (PowerShell), macOS, Linux — all three must work from day 1

**Performance Goals**:
- Pre-flight validation completes in under 5 seconds
- All services ready for a first chat request within 3 minutes of `just dev`

**Constraints**:
- No `.sh` scripts in the developer workflow — all logic in Python or `just` recipes
- Docker manages PostgreSQL and MLflow only; FastAPI and Next.js run as native processes
- Single `.env.example` as the source of truth for all environment variable documentation

**Scale/Scope**: Single-developer machine; 4 services total (PostgreSQL, MLflow, FastAPI, Next.js)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| No prompt strings hardcoded in Python (Principle VI) | N/A | No LLM calls in this feature |
| No Sitecore write without user confirmation (Principle I) | N/A | No Sitecore integration in this feature |
| New integrations use typed API client layer (Principle VII) | N/A | No external API integrations |
| New task behaviors in `instructions/tasks/*.md` (Principle VI) | N/A | No new AI tasks |
| No profile-switching logic (Principle IV) | N/A | No instruction system changes |
| Guardrail coverage verified (Principle II) | N/A | No guardrail changes |
| Memory writes use correct store (Principle V) | N/A | No new DB entities |
| LLM calls only through `clients/llm.py` (Technology Standards) | N/A | No LLM calls |
| LangGraph graphs in `services/`, tools in `clients/` (Technology Standards) | N/A | No orchestration changes |
| MLflow tracing on all LLM/LangGraph call paths (Principle VII) | N/A | No new LLM call paths |
| Single `CLAUDE.md` at project root (Governance) | ✅ PASS | Root file exists; `.claude/CLAUDE.md` removed in prior session |
| DRY: single configuration template (Principle III) | ✅ PASS | `.env.example` is the single source of truth for all service variables |

## Project Structure

### Documentation (this feature)

```text
specs/002-local-dev-environment/
├── plan.md              # This file
├── research.md          # Phase 0 research decisions
├── quickstart.md        # Validation guide
├── contracts/
│   └── commands.md      # Developer command interface contracts
└── tasks.md             # Created by /speckit-tasks
```

### Source Code (new files for this feature)

```text
docker/                            # Pre-existing — Docker infra config (do not move)
├── docker-compose.yml          # PostgreSQL (supabase/postgres:17.6.1.067) + MLflow
├── .env.example                # Docker credential template (POSTGRES_USER/PASSWORD/DB)
└── .env                        # Actual Docker credentials (gitignored)

scripts/
├── preflight.py                # Validate env vars + check port availability before launch
└── wait_for_db.py              # Poll PostgreSQL until it accepts connections

Justfile                        # Developer recipes: dev, stop, reset, logs
Procfile.dev                    # honcho: backend, frontend processes with unified logs
.env.example                    # Complete variable template for all services (all annotated)
```

**No changes to `backend/` or `frontend/` source trees in this feature** (the feature wires them together; it does not modify them).

## Key Implementation Decisions

### Startup Sequence

`just dev` executes these steps in order, aborting on any non-zero exit:

```
1. python scripts/preflight.py          # env var check → port check → exits 0 or named error
2. docker compose -f docker/docker-compose.yml up -d  # PostgreSQL + MLflow
3. python scripts/wait_for_db.py        # SQLAlchemy retry (tenacity, up to 90 s)
4. cd backend && alembic upgrade head   # apply all pending migrations
5. honcho start -f Procfile.dev         # FastAPI (8000) + Next.js (3000) with unified logs
```

### Pre-flight Script (`scripts/preflight.py`)

Validates in two passes before any service starts:

**Pass 1 — Required env vars**:
- Loads `.env` via `python-dotenv`
- Checks a hardcoded list of required secrets (currently: `LLM_API_KEY`)
- Exits `1` on first missing variable: `ERROR: LLM_API_KEY is required but not set`

**Pass 2 — Port availability**:
- Checks ports 3000, 5000, 5432, 8000 using `socket.connect_ex()`
- Exits `1` on first blocked port: `ERROR: port 8000 is in use (required by: FastAPI backend)`
- All four ports checked sequentially; first conflict found is named

### DB Readiness Script (`scripts/wait_for_db.py`)

Uses `tenacity` + synchronous `sqlalchemy.create_engine`:

```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from sqlalchemy import create_engine, text
import sqlalchemy.exc, os

@retry(
    stop=stop_after_attempt(30),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def _connect(url: str) -> None:
    engine = create_engine(url, connect_args={"connect_timeout": 5})
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    engine.dispose()

def main() -> None:
    url = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://", 1)
    print("Waiting for database...")
    _connect(url)
    print("✓ Database ready")
```

### Procfile.dev

```procfile
backend: cd backend && uvicorn app.main:app --reload --port 8000
frontend: cd frontend && npm run dev
```

Docker service logs are accessed via `just logs` (a separate recipe streaming `docker compose logs -f`). This keeps the honcho terminal clean — application logs only.

### docker/docker-compose.yml (pre-existing)

The `docker/` directory already contains a working Docker Compose setup — **do not recreate it**. The existing services:

- **postgres**: `supabase/postgres:17.6.1.067` — Supabase-flavored PostgreSQL 17 with extensions (PostGIS, pgvector, etc.)
- **mlflow**: `ghcr.io/mlflow/mlflow:v2.19.0` — MLflow tracking server with SQLite backend store and artifact serving

Credentials are read from `docker/.env` (gitignored). See `docker/.env.example` for the required variables: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`.

> **Version note**: The constitution requires `mlflow>=2.21.0` for `mlflow.langchain.autolog()` support. The current image (`v2.19.0`) predates this API. **Update the image tag to `v2.21.0`** in `docker/docker-compose.yml` before running the LangGraph tracing feature.

### Justfile

```just
# Default: list available recipes
default:
    @just --list

# Start the full local stack
dev:
    python scripts/preflight.py
    docker compose -f docker/docker-compose.yml up -d
    python scripts/wait_for_db.py
    cd backend && alembic upgrade head
    honcho start -f Procfile.dev

# Stop Docker containers (Ctrl+C stops honcho; this handles detached cleanup)
stop:
    docker compose -f docker/docker-compose.yml stop

# Drop and recreate all DB tables from scratch (Docker volume preserved)
reset:
    cd backend && alembic downgrade base && alembic upgrade head

# Stream Docker infra logs (Postgres + MLflow)
logs:
    docker compose -f docker/docker-compose.yml logs -f
```

### Service Topology Enforcement

FR-002 (backend internal-only) is enforced by Next.js proxy configuration — already specified in the 001-core-chat-app plan:
- FastAPI binds to `0.0.0.0:8000` locally (necessary for Docker networking)
- Next.js API routes proxy all `/api/*` requests to `http://localhost:8000` in local mode
- No browser can reach `localhost:8000` directly in the expected UX because the frontend is the intended entry point — the backend is _accessible_ but all app UI routes through the proxy
- This mirrors Railway topology where FastAPI has no public domain

### Hot Reload

- **FastAPI**: `uvicorn app.main:app --reload` watches `backend/app/` for changes; reloads automatically
- **Next.js**: `next dev` provides hot module replacement; browser reflects changes without manual refresh

Both are already supported by the respective frameworks — no additional configuration needed.

### Configuration Split

There are two `.env` files in this setup:

| File | Purpose | Committed? |
|------|---------|------------|
| `docker/.env` | Docker container credentials (`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`) | No — gitignored; template at `docker/.env.example` |
| `.env` (root) | Application configuration for all services | No — gitignored; template at `.env.example` |

The `scripts/preflight.py` loads the root `.env`. The `DATABASE_URL` in the root `.env` must use the same credentials as `docker/.env`.

### .env.example Structure

```bash
# ─────────────────────────────────────────────────────────────────────────────
# LOCAL DEVELOPMENT CONFIGURATION
# Copy this file to .env and fill in all SECRET values before running `just dev`
# ─────────────────────────────────────────────────────────────────────────────

# ── LLM ────────────────────────────────────────────────────────────────────────
# SECRET: requires a real value — startup will refuse if missing
LLM_API_KEY=

# DEFAULT: safe for local dev
LLM_MODEL=gpt-4o-mini
# LLM_BASE_URL=   # Optional: override for alternative providers (e.g., Azure, Ollama)

# ── Database ─────────────────────────────────────────────────────────────────
# DEFAULT: matches docker-compose.yml service defaults
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/marketing_app

# ── Runtime context ───────────────────────────────────────────────────────────
# DEFAULT: disables Sitecore OAuth and iframe context for local development
RUNTIME_CONTEXT=local

# DEFAULT: stub Sitecore context values — used when RUNTIME_CONTEXT=local
LOCAL_PAGE_ID=stub-page-id
LOCAL_SITE_ID=stub-site-id
LOCAL_LANGUAGE=en

# ── Service URLs ─────────────────────────────────────────────────────────────
# DEFAULT: Next.js proxies to the local FastAPI instance
API_URL=http://localhost:8000

# ── MLflow ───────────────────────────────────────────────────────────────────
# DEFAULT: write traces to local filesystem; open http://localhost:5000 to view
MLFLOW_TRACKING_URI=http://localhost:5000
```

## Complexity Tracking

> No constitution violations. No complexity justifications required.

## Post-Design Constitution Check

All applicable gates re-verified. All N/A gates confirmed not applicable to a dev tooling feature. Both active gates (single CLAUDE.md, DRY config template) pass.
