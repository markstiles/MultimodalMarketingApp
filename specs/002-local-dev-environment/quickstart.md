# Quickstart Validation Guide: Local Development Environment

**Feature**: `002-local-dev-environment`
**Date**: 2026-06-17

This guide walks through the validation scenarios that confirm the local dev environment works end-to-end. See [plan.md](plan.md) for implementation details and [contracts/commands.md](contracts/commands.md) for the full command reference.

---

## Prerequisites

Before running any validation, ensure:

- [ ] `just` is installed (`winget install just` on Windows; `brew install just` on macOS)
- [ ] **Windows only**: Git for Windows installed — provides `sh`, which `just` requires for `&&` operators in Justfile recipes (`winget install Git.Git`)
- [ ] Docker Desktop is running
- [ ] Python 3.12 venv created and activated at `backend/.venv` (`cd backend && python -m venv .venv`, then activate with `backend\.venv\Scripts\Activate.ps1` on Windows or `source backend/.venv/bin/activate` on macOS/Linux)
- [ ] `pip install honcho tenacity` (dev dependencies)
- [ ] Node.js 20+ installed; `cd frontend && npm install` completed
- [ ] `.env` file created from `.env.example` with `LLM_API_KEY` set

---

## Scenario 1: Full Stack Startup (FR-001, SC-001)

**Goal**: Confirm all services start from a single command within 3 minutes.

**Command**:
```
just dev
```

**Expected output (in order)**:
```
✓ Environment OK
✓ Ports OK
[Docker] Creating postgres ... done
[Docker] Creating mlflow ... done
Waiting for database...
✓ Database ready
INFO  [alembic.runtime.migration] Running upgrade  -> <revision>
[honcho] 12:00:00 backend  | INFO:     Application startup complete.
[honcho] 12:00:01 frontend | ▶ Ready on http://localhost:3000
```

**Validation**:
- [ ] Terminal shows all four services running
- [ ] `http://localhost:3000` loads the chat UI in the browser
- [ ] `http://localhost:5000` loads the MLflow tracking UI

**Timing**: All services ready in under 3 minutes (SC-001 target: 10 minutes from clone).

---

## Scenario 2: End-to-End Chat Request (User Story 1 AS-2)

**Goal**: Confirm a chat message sent through the frontend produces a streamed response.

**Precondition**: Scenario 1 complete.

**Steps**:
1. Open `http://localhost:3000` in a browser
2. Type a message and submit

**Validation**:
- [ ] Response streams back token-by-token in the UI
- [ ] Backend logs in the honcho terminal show the LangGraph trace

---

## Scenario 3: Service Topology (FR-002, SC-005)

**Goal**: Confirm the backend is not directly accessible from the browser, matching production topology.

**Precondition**: Scenario 1 complete.

**Steps**:
1. In a browser, navigate to `http://localhost:8000/health`

**Validation**:
- [ ] The request returns a `200 OK` with the health payload — **this is expected** locally (FastAPI binds to `0.0.0.0:8000` so the port is technically reachable)

> **Note**: The topology enforcement in local mode is behavioral, not network-level. FastAPI is accessible at localhost:8000, but the application UI exclusively uses the Next.js proxy at port 3000. Production enforcement comes from Railway's internal network (no public FastAPI domain). SC-005 is validated by confirming all application traffic flows through `localhost:3000`, not by blocking direct access.

- [ ] All chat requests in the UI go through `localhost:3000/api/chat` (visible in browser DevTools → Network tab)

---

## Scenario 4: Pre-flight Validation (FR-001 fail-fast behavior)

**Goal**: Confirm the stack refuses to start when configuration is missing.

**Test A — Missing secret**:
1. In `.env`, comment out `LLM_API_KEY`
2. Run `just dev`

**Expected**:
```
ERROR: LLM_API_KEY is required but not set
```
- [ ] Process exits immediately; no Docker containers started

**Test B — Port conflict**:
1. Start any process on port 8000 (e.g., `python -m http.server 8000`)
2. Run `just dev`

**Expected**:
```
ERROR: port 8000 is in use (required by: FastAPI backend)
```
- [ ] Process exits immediately; no Docker containers started
3. Stop the conflicting process and restore `.env`

---

## Scenario 5: Hot Reload — Backend (FR-006, SC-003)

**Goal**: Confirm a Python change is live within 5 seconds.

**Precondition**: Stack running via `just dev`.

**Steps**:
1. Open `backend/app/api/chat.py` (or any route file)
2. Add a comment or harmless whitespace change and save

**Expected** in honcho terminal:
```
[honcho] backend | WARNING:  StatReload detected file change in 'app/api/chat.py'. Reloading...
[honcho] backend | INFO:     Application startup complete.
```
- [ ] Reload appears within 5 seconds
- [ ] Chat requests still work after reload

---

## Scenario 6: Hot Reload — Frontend (FR-007, SC-004)

**Goal**: Confirm a TypeScript/TSX change appears in the browser without a manual refresh.

**Precondition**: Stack running; `http://localhost:3000` open in browser.

**Steps**:
1. Open `frontend/components/ChatPanel.tsx` (or any component)
2. Change a string literal and save

**Expected**:
- [ ] Browser reflects the change within 3 seconds (Next.js HMR)
- [ ] No manual page refresh required

---

## Scenario 7: Database Reset (FR-008)

**Goal**: Confirm `just reset` drops and recreates all tables without affecting Docker or other services.

**Precondition**: Stack running; at least one conversation exists in the database.

**Commands** (run in a second terminal while stack is up):
```
just reset
```

**Expected output**:
```
INFO  [alembic.runtime.migration] Running downgrade <revision> -> ...
INFO  [alembic.runtime.migration] Running upgrade ... -> <revision>
```

**Validation**:
- [ ] Alembic downgrade + upgrade completes without error
- [ ] The chat UI at `http://localhost:3000` still loads (frontend unaffected)
- [ ] New conversation created via UI works (schema is correct)
- [ ] Previous conversation data is gone (tables were dropped)
- [ ] `docker ps` confirms PostgreSQL container still running

---

## Scenario 8: Unified Logs (FR-009)

**Goal**: Confirm all application logs appear in one terminal.

**Precondition**: Stack running via `just dev`.

**Steps**:
1. Send a chat message through the UI
2. Observe the honcho terminal

**Validation**:
- [ ] Both `[backend]` and `[frontend]` prefixed log lines appear in the same terminal
- [ ] Request flow is traceable end-to-end in a single view

---

## Scenario 9: MLflow Trace Visibility (FR-010)

**Goal**: Confirm LLM traces appear in the MLflow UI.

**Precondition**: Scenario 2 complete (at least one chat request sent).

**Steps**:
1. Open `http://localhost:5000` in the browser
2. Navigate to the experiment created by the backend

**Validation**:
- [ ] At least one run is listed
- [ ] Run contains LangGraph node traces (model call, tool calls if any)
- [ ] Token counts and latency are recorded

---

## Scenario 10: Failed Migration Abort (FR-003)

**Goal**: Confirm a migration failure aborts the full stack (not just the migration step).

> This scenario requires temporarily introducing a bad migration. Do not perform this on a shared machine.

**Steps**:
1. Create a broken migration in `backend/alembic/versions/` (e.g., invalid SQL in `upgrade()`)
2. Run `just dev`

**Expected**:
- [ ] Alembic error output is shown in full before any other service starts
- [ ] honcho does NOT start (FastAPI and Next.js do not appear)
3. Remove the broken migration file and confirm `just dev` succeeds again
