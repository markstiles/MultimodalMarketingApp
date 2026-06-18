# Tasks: Local Development Environment

**Input**: Design documents from `specs/002-local-dev-environment/`

**Prerequisites**: plan.md ✅ · spec.md ✅ · research.md ✅ · contracts/commands.md ✅

**Tests**: Not requested in spec — no test tasks generated.

**Organization**: Tasks are grouped by user story. Each story is independently completable and testable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no incomplete dependencies)
- **[Story]**: User story this task belongs to ([US1], [US2], [US3])
- All file paths are relative to the project root

---

## Phase 1: Setup — Docker Config & Dev Dependencies

**Purpose**: Prepare existing infrastructure files and install tooling dependencies before any story work begins.

- [x] T001 Update `docker/docker-compose.yml` — MLflow image remains at `v2.19.0`; `v2.21.0` has no `linux/amd64` manifest in ghcr.io. Version upgrade deferred to feature 001 when `mlflow.langchain.autolog()` is wired up and a compatible image can be verified.
- [x] T002 [P] Add `healthcheck` block to the `postgres` service in `docker/docker-compose.yml`: `test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]`, `interval: 5s`, `timeout: 5s`, `retries: 5` — used by `wait_for_db.py` to confirm container readiness
- [x] T003 [P] Create `backend/requirements-dev.txt` — add `honcho`, `tenacity`, and `python-dotenv` as dev-only dependencies (install with `pip install -r backend/requirements-dev.txt`); note that `sqlalchemy` is already an indirect dependency via `sqlmodel`

**Checkpoint**: Docker config updated, Python dev deps file ready to install.

---

## Phase 2: Foundational (Blocking Prerequisite)

**Purpose**: Verify the Docker credential template is in a format that `docker compose` can actually read before any script work begins. This phase is independent of Phase 1 and can run in parallel with it.

**⚠️ CRITICAL**: Faulty `docker/.env` format will silently pass wrong credentials to PostgreSQL, breaking `wait_for_db.py` in Phase 3.

- [x] T004 [P] Audit `docker/.env.example` — confirm every line uses `KEY=value` format (not YAML `KEY: value`); rewrite any `: ` lines to `=`; verify the three variables (`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`) use values that will match the `DATABASE_URL` default planned for root `.env.example` (e.g., `POSTGRES_USER=postgres`, `POSTGRES_PASSWORD=postgres`, `POSTGRES_DB=marketing_app`)

**Checkpoint**: `docker/.env.example` format verified — copy to `docker/.env` and `docker compose up -d` should start both services without credential errors.

---

## Phase 3: User Story 1 — Full Stack Local Startup (Priority: P1) 🎯 MVP

**Goal**: A developer runs `just dev` and all four services start in order with a single command. Pre-flight catches missing secrets and port conflicts before any service launches. A failed migration aborts the full stack. Unified logs appear in one terminal.

**Independent Test**: Run `just dev` on a clean machine; confirm the terminal shows the 5-step startup sequence, all four services are running, and `http://localhost:3000` loads. Run `just dev` again while running — pre-flight must detect the port conflicts and exit immediately.

### Implementation for User Story 1

- [x] T005 [P] [US1] Create `scripts/preflight.py` — Pass 1 (env vars): load root `.env` with `python-dotenv` (`load_dotenv()`); define `REQUIRED_SECRETS = ["LLM_API_KEY"]`; iterate and exit 1 with `ERROR: {var} is required but not set` on first missing or empty value; print `✓ Environment OK` on success
- [x] T006 [US1] Extend `scripts/preflight.py` — Pass 2 (port check): define `REQUIRED_PORTS = [(3000, "Next.js frontend"), (5000, "MLflow"), (5432, "PostgreSQL"), (8000, "FastAPI backend")]`; for each, attempt `socket.connect_ex(("127.0.0.1", port))`; exit 1 with `ERROR: port {n} is in use (required by: {service})` on first conflict; print `✓ Ports OK` on success (depends on T005 — same file)
- [x] T007 [P] [US1] Create `scripts/wait_for_db.py` — import `tenacity`, `sqlalchemy`; decorate `_connect()` with `@retry(stop=stop_after_attempt(30), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)`; inside `_connect()`, build sync URL by replacing `postgresql+asyncpg://` with `postgresql://` in `DATABASE_URL`; call `create_engine(url).connect()` and `execute(text("SELECT 1"))`; `main()` prints `Waiting for database...` before retry and `✓ Database ready` on success; on timeout reraise prints attempt count and exits 1
- [x] T008 [P] [US1] Create `Procfile.dev` — two lines: `backend: cd backend && uvicorn app.main:app --reload --reload-dir app --port 8000` and `frontend: cd frontend && npm run dev` (the `--reload-dir app` flag scopes uvicorn's file watcher to `backend/app/` only, preventing reloads on `.env` or migration file changes)
- [x] T009 [US1] Create `Justfile` at project root with five recipes matching `contracts/commands.md` exactly: `default` (`@just --list`), `dev` (5-step sequence: `python scripts/preflight.py` → `docker compose -f docker/docker-compose.yml up -d` → `python scripts/wait_for_db.py` → `cd backend && alembic upgrade head` → `honcho start -f Procfile.dev`, followed by `@echo "✓ Stack ready — http://localhost:3000"` as the final line of the recipe per FR-001 ready-signal requirement), `stop` (`docker compose -f docker/docker-compose.yml stop`), `reset` (`cd backend && alembic downgrade base && alembic upgrade head`), `logs` (`docker compose -f docker/docker-compose.yml logs -f`) — each step in `dev` on its own line so `just` exits the recipe on any non-zero return

**FR-002 coverage note**: FR-002 (backend-internal topology — all application traffic routes through the Next.js proxy on port 3000) is owned by the feature 001 Next.js proxy configuration. T015 Scenario 3 verifies it is in place during end-to-end validation; no US1 task directly implements it.

**Checkpoint**: `just dev` completes the 5-step sequence, honcho terminal shows `[backend]` and `[frontend]` log prefixes, `http://localhost:3000` and `http://localhost:5000` are accessible, `just reset` drops and recreates tables without stopping other services.

---

## Phase 4: User Story 2 — Environment Configuration Parity (Priority: P2)

**Goal**: A developer opening the repo for the first time can read `.env.example` and know exactly which variables require real secrets versus safe defaults, with no deployed variable left undocumented.

**Independent Test**: Compare `.env.example` against the deployed service variable list in Railway; every variable in every Railway service must have a matching entry. A new developer should be able to copy `.env.example` to `.env`, fill in only `LLM_API_KEY`, and run `just dev` successfully.

### Implementation for User Story 2

- [x] T010 [P] [US2] Create root `.env.example` — five service sections with comment headers (`LLM`, `Database`, `Runtime Context`, `Service URLs`, `MLflow`); mark `LLM_API_KEY=` as `# SECRET: requires a real value — startup will refuse if missing`; mark all other variables as `# DEFAULT: safe for local dev` with their default values pre-filled; include every variable from the environment reference table in `contracts/commands.md`: `LLM_API_KEY`, `LLM_MODEL`, `LLM_BASE_URL` (commented out), `DATABASE_URL`, `RUNTIME_CONTEXT`, `LOCAL_PAGE_ID`, `LOCAL_SITE_ID`, `LOCAL_LANGUAGE`, `API_URL`, `MLFLOW_TRACKING_URI`
- [x] T011 [US2] Update `docker/.env.example` — apply the T004 format fix if not already done; add inline comments explaining each variable (`# PostgreSQL superuser username`, etc.); ensure `POSTGRES_DB` default matches the database name in `DATABASE_URL` from T010 (both should use `marketing_app`)

**Checkpoint**: A developer can copy `.env.example` → `.env`, set `LLM_API_KEY`, and `just dev` succeeds. `docker/.env.example` copy → `docker/.env` starts PostgreSQL with credentials that match `DATABASE_URL`.

---

## Phase 5: User Story 3 — Hot Reload for Active Development (Priority: P3)

**Goal**: Saving a Python file in `backend/app/` reloads the FastAPI server within 5 seconds. Saving a TypeScript file in `frontend/` updates the browser without a manual refresh.

**Independent Test**: With `just dev` running, modify a return value in any backend route and save — uvicorn reload message appears in the `[backend]` log within 5 seconds. Modify a text string in any frontend component and save — browser reflects the change without refreshing.

### Implementation for User Story 3

- [x] T012 [P] [US3] Verify `frontend/package.json` contains `"dev": "next dev"` in the `scripts` section; add it if absent — honcho invokes this script via `npm run dev` in `Procfile.dev`
- [x] T013 [US3] Verify `backend/app/main.py` exists and exports a `app` FastAPI instance (the `app.main:app` uvicorn target in `Procfile.dev`); if the entry point differs, update the `backend` line in `Procfile.dev` to match the actual module path

**Checkpoint**: Modifying `backend/app/api/chat.py` and saving causes a uvicorn reload message within 5 seconds. Modifying a frontend component and saving causes a Next.js HMR update in the browser without page refresh.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [x] T014 [P] Update `docker/README.md` — add a note at the top that this folder integrates with `just dev` from the project root; update any references to the old `dev/` folder name; add `just` to the prerequisites list alongside Docker Desktop
- [ ] T015 Run all validation scenarios from `quickstart.md` (Scenarios 1–10) manually to confirm end-to-end stack health; check off each scenario as passing — stop and address any failing scenario before continuing; do not skip ahead to mark T015 complete while any scenario is unresolved

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately; T002 and T003 are parallel
- **Phase 2 (Foundational)**: Independent of Phase 1 — can run in parallel (T004 audits `docker/.env.example` format, not the MLflow/healthcheck changes from T001/T002)
- **Phase 3 (US1)**: Depends on Phase 2 — T005/T007/T008 are parallel; T006 depends on T005 (same file); T009 depends on T008 (references `Procfile.dev`)
- **Phase 4 (US2)**: Independent of US1 — can begin after Phase 2; T010 and T011 are parallel
- **Phase 5 (US3)**: Depends on T008/T009 (Procfile.dev and Justfile must exist to validate hot reload paths)
- **Phase 6 (Polish)**: Depends on all previous phases complete

### User Story Dependencies

- **US1 (P1)**: Depends only on Phase 2 completion
- **US2 (P2)**: Independent of US1 — can run in parallel with US1 after Phase 2
- **US3 (P3)**: Depends on US1 completion (Procfile.dev must exist)

### Within User Story 1

- T005 before T006 (same file — Pass 1 then Pass 2)
- T007 and T008 can run in parallel with T005/T006 (different files)
- T009 after T008 (Justfile references `Procfile.dev` filename)

---

## Parallel Execution Examples

### Phase 1 (all three in parallel)
```
T001: Update docker/docker-compose.yml MLflow version
T002: Add PostgreSQL healthcheck to docker/docker-compose.yml
T003: Create backend/requirements-dev.txt
```

### Phase 3 — US1 (first wave in parallel)
```
T005: Create scripts/preflight.py (Pass 1 — env vars)
T007: Create scripts/wait_for_db.py
T008: Create Procfile.dev
```
Then sequentially:
```
T006: Extend scripts/preflight.py (Pass 2 — ports)  ← after T005
T009: Create Justfile                                ← after T008
```

### Phase 4 — US2 (in parallel with US1 Phase 3)
```
T010: Create root .env.example
T011: Update docker/.env.example
```

---

## Implementation Strategy

### MVP (User Story 1 Only)

1. Complete Phase 1 (Setup) — 3 tasks
2. Complete Phase 2 (Foundational) — 1 task
3. Complete Phase 3 (US1) — 5 tasks
4. **STOP AND VALIDATE**: `just dev` starts the full stack; pre-flight catches errors; `just reset` works
5. US2 and US3 add polish but do not block the working local dev loop

### Incremental Delivery

1. Phase 1 + Phase 2 → infrastructure ready
2. US1 → full `just dev` command working → **demo-able milestone**
3. US2 → `.env.example` documented → onboarding unblocked
4. US3 → hot reload verified → active development ready
5. Phase 6 → polish and full quickstart validation

---

## Notes

- [P] tasks operate on different files and have no incomplete dependencies
- [US1]/[US2]/[US3] labels map tasks to their user story for traceability
- No test tasks generated — spec does not request TDD; quickstart.md (T015) covers validation
- `docker/.env` is gitignored — `docker/.env.example` is the committed template; both files must stay in sync
- `scripts/preflight.py` uses the root `.env` — developers must copy `.env.example` → `.env` before `just dev`
- `sqlalchemy` sync engine in `scripts/wait_for_db.py` is intentionally separate from the async engine in `backend/app/resources/database.py` — startup scripts run outside the async event loop
