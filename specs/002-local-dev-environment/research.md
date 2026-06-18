# Research: Local Development Environment

**Feature**: `002-local-dev-environment`
**Date**: 2026-06-17

---

## Decision 1: Process Orchestration

**Decision**: `just` (task runner) + `honcho` (process manager)

**Rationale**: `just` is a Rust-based single binary available for Windows, macOS, and Linux with no toolchain dependencies. It provides the developer-facing command vocabulary (`just dev`, `just reset`, `just stop`). `honcho` is a Python package (Procfile runner, port of Heroku's Foreman) that multiplexes stdout/stderr from all native processes to a single terminal window with color-coded, named prefixes. Since the project already requires Python, `honcho` adds no new language runtime.

**Alternatives considered**:
- **GNU Makefile**: Native on Mac/Linux but unreliable on Windows without GnuWin32 or WSL. Ruled out — team is Windows-first.
- **Honcho alone**: Excellent process multiplexer but provides no named recipe interface for `reset`, `stop`, etc.
- **process-compose**: TUI-based orchestrator with `depends_on` health checks and Windows support. Well-suited, but requires installing a separate Go binary and a YAML process config. The Procfile format (honcho) is simpler and more widely understood.
- **Shell scripts only**: Bash/PowerShell syntax divergence creates maintenance burden. Ruled out — all orchestration logic lives in Python scripts instead.

---

## Decision 2: Database Readiness Polling

**Decision**: Synchronous SQLAlchemy connection retry via `tenacity`

**Rationale**: The backend runs natively (not in Docker), so Docker's `depends_on: condition: service_healthy` cannot reach the host Python process. A synchronous `create_engine` + retry loop is pure Python, zero additional tools, and tests actual connection acceptance (not just TCP port open). `tenacity` provides exponential backoff with configurable attempts and human-readable failure messages.

**Retry parameters**:
| Parameter | Value |
|-----------|-------|
| Max attempts | 30 |
| Backoff | Exponential, min 2 s, max 10 s |
| Connection timeout (per attempt) | 5 s |
| Worst-case total wait | ~90 s |

**Alternatives considered**:
- **`pg_isready` subprocess**: Requires PostgreSQL client tools on the developer machine — additional install, especially painful on Windows.
- **`wait-for-it.sh` / `dockerize`**: Shell script or Go binary; not portable on Windows natively.
- **asyncpg retry**: Async context adds unnecessary complexity for a startup script; sync driver is sufficient here.
- **Docker healthcheck polling via `docker inspect`**: Indirect — the Docker healthcheck passes when PostgreSQL is up at the OS level, but the retry loop tests an actual SQL connection, which is what Alembic needs.

---

## Decision 3: Pre-flight Validation

**Decision**: Python script `scripts/preflight.py`

**Rationale**: Pure Python is cross-platform. The script runs before any service starts and exits with a non-zero code and a named error message for each problem found. Port availability is checked via Python's `socket` stdlib. Environment variables are loaded from `.env` via `python-dotenv` (already a dev dependency).

**Checked items (in order)**:
1. Required env vars present and non-empty — names the first missing variable and exits immediately
2. Required ports not already bound — names the blocked port and the service that needs it

**Port assignments**:
| Port | Service |
|------|---------|
| 3000 | Next.js frontend |
| 5000 | MLflow tracking UI |
| 5432 | PostgreSQL |
| 8000 | FastAPI backend |

---

## Decision 4: Cross-Platform Compatibility

**Decision**: `just` for commands + Python scripts for all logic; no `.sh` files in the developer workflow

**Rationale**: `just` generates the correct shell invocation per platform (PowerShell on Windows, bash on Mac/Linux). All orchestration logic is in Python scripts — inherently cross-platform. Docker Compose V2 (`docker compose`) works identically on all platforms. No `.sh` scripts needed.

---

## Decision 5: Configuration Template

**Decision**: Single `.env.example` at the project root covering all services

**Rationale**: Satisfies FR-004 (single template) and the constitution's DRY principle. Organized by service section. Each variable is annotated as either `# SECRET: requires a real value` or `# DEFAULT: safe for local dev`. Developer copies `.env.example` to `.env`, fills in secrets, and runs `just dev`. The pre-flight script reads this `.env` and validates required variables before any service launches.

---

## Resolved Unknowns

| Unknown | Resolution |
|---------|------------|
| Process orchestration tool | `just` + `honcho` |
| DB readiness polling | `tenacity` retry with synchronous SQLAlchemy |
| Pre-flight validation | `scripts/preflight.py` (Python + stdlib socket) |
| Cross-platform strategy | Python scripts for logic; `just` for recipes |
| Windows log multiplexing | `honcho` works in single PowerShell terminal |
