# Developer Command Contracts: Local Development Environment

**Feature**: `002-local-dev-environment`
**Date**: 2026-06-17

All commands are defined in `Justfile` at the project root and invoked as `just <recipe>`.

---

## `just dev`

**Purpose**: Start the full local stack (infrastructure + application services).

**Preconditions**:
- Docker Desktop is running
- `.env` file exists at project root (copy from `.env.example` and fill in secrets)
- `just` is installed (`brew install just` / `winget install just`)
- Python 3.12 venv activated (`source backend/.venv/bin/activate` or equivalent)
- Node.js dependencies installed (`cd frontend && npm install`)

**Execution sequence**:
1. `python scripts/preflight.py` — validates all required env vars and checks that ports 3000, 5000, 5432, 8000 are free; exits non-zero with a named error if anything fails
2. `docker compose -f docker/docker-compose.yml up -d` — starts PostgreSQL (port 5432) and MLflow (port 5000) in detached mode
3. `python scripts/wait_for_db.py` — polls PostgreSQL until it accepts connections (up to 90 s); exits non-zero if timeout exceeded
4. `cd backend && alembic upgrade head` — applies all pending migrations; exits non-zero and surfaces full error output on failure, aborting the stack
5. `honcho start -f Procfile.dev` — starts FastAPI (port 8000) and Next.js (port 3000) with unified, color-coded log output in the current terminal

**Success output**:
- Pre-flight: `✓ Environment OK` / `✓ Ports OK`
- DB wait: `✓ Database ready`
- Migrations: Alembic upgrade output ending in `Running upgrade … → <revision>`
- `honcho` starts prefixing backend and frontend log lines in the terminal

**Failure modes**:

| Condition | Behavior |
|-----------|----------|
| Missing required env var | `preflight.py` exits 1: `ERROR: LLM_API_KEY is required but not set` |
| Port already bound | `preflight.py` exits 1: `ERROR: port 8000 is in use (required by: FastAPI backend)` |
| DB not ready after 90 s | `wait_for_db.py` exits 1: `ERROR: Could not connect to PostgreSQL after 30 attempts` |
| Alembic migration fails | `alembic upgrade head` exits non-zero; full traceback is shown; honcho does not start |
| honcho process crash | Affected process log line shown in terminal; other processes continue running |

**Postconditions**:
- PostgreSQL and MLflow containers running (`docker ps` confirms)
- FastAPI listening at `http://localhost:8000` (internal only — not browsable directly)
- Next.js listening at `http://localhost:3000` (browser entry point)
- MLflow UI accessible at `http://localhost:5000`

---

## `just stop`

**Purpose**: Stop all running local stack processes and Docker containers.

**Preconditions**: Stack was started with `just dev`

**Execution**:
1. `honcho` is terminated by pressing `Ctrl+C` in the terminal running `just dev` (honcho handles this via SIGINT — both native processes exit cleanly)
2. `just stop` is a separate recipe that stops Docker containers when honcho is not in the foreground: `docker compose -f docker/docker-compose.yml stop`

**Postconditions**: All four services stopped; Docker volumes preserved (database data retained)

---

## `just reset`

**Purpose**: Drop all database tables and re-run all migrations from scratch, leaving the database empty but schema-current.

**Preconditions**:
- PostgreSQL container is running (`docker ps` or `just dev` started previously)
- `DATABASE_URL` env var set (loaded from `.env`)

**Execution sequence**:
1. `cd backend && alembic downgrade base` — drops all managed tables in reverse migration order
2. `cd backend && alembic upgrade head` — re-creates all tables from scratch

**Postconditions**:
- All tables dropped and recreated (empty)
- Docker volume preserved (PostgreSQL process remains running)
- Other services (Next.js, FastAPI, MLflow) are unaffected

**Failure modes**:

| Condition | Behavior |
|-----------|----------|
| PostgreSQL not running | `alembic downgrade` fails; full error shown |
| Migration fails mid-reset | Schema left in partially downgraded state; error shown with revision that failed |

---

## `just logs`

**Purpose**: Stream live logs from Docker-managed services (PostgreSQL, MLflow) when the stack is running detached.

**Note**: Application logs (FastAPI, Next.js) are shown inline in the `just dev` terminal via honcho. This recipe is for Docker infra logs only.

**Execution**: `docker compose -f docker/docker-compose.yml logs -f`

**Postconditions**: Live log stream from PostgreSQL and MLflow in current terminal. `Ctrl+C` to exit without stopping containers.

---

## Environment Variables Reference

Documented in `.env.example` at the project root. Each variable is annotated as `SECRET` (requires a real value) or `DEFAULT` (safe for local dev).

**Required secrets** (pre-flight enforces presence):

| Variable | Service | Notes |
|----------|---------|-------|
| `LLM_API_KEY` | Backend | OpenAI or compatible API key |

**Variables with safe local defaults** (pre-flight allows missing):

| Variable | Service | Local default |
|----------|---------|---------------|
| `DATABASE_URL` | Backend | `postgresql://postgres:postgres@localhost:5432/marketing_app` |
| `LLM_MODEL` | Backend | `gpt-4o-mini` |
| `RUNTIME_CONTEXT` | Frontend | `local` |
| `LOCAL_PAGE_ID` | Frontend | `stub-page-id` |
| `LOCAL_SITE_ID` | Frontend | `stub-site-id` |
| `LOCAL_LANGUAGE` | Frontend | `en` |
| `API_URL` | Frontend | `http://localhost:8000` |
| `MLFLOW_TRACKING_URI` | Backend | `http://localhost:5000` |
