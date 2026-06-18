# Feature Specification: Local Development Environment

**Feature Branch**: `002-local-dev-environment`

**Created**: 2026-06-17

**Status**: Draft

**Input**: User description: "the local system will run with the assistance of a docker container for the postgres database. i want to make sure that it will properly simulate as much of the deployed system locally as possible."

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Full Stack Local Startup (Priority: P1)

A developer clones the repository on a clean machine and starts all application services with a single command. Within minutes, every service is running and they can send a chat request through the frontend just as a user would in production. The backend is not directly accessible — all traffic goes through the frontend, matching the deployed topology.

**Why this priority**: This is the foundation of the local dev experience. If the stack doesn't start cleanly and mirror the deployed topology, all other local development work is unreliable.

**Independent Test**: Can be fully tested by cloning the repo on a machine that has never run the project, running a single startup command, and confirming a chat message sent through the frontend receives a streamed response — with the backend unreachable directly.

**Acceptance Scenarios**:

1. **Given** a clean machine with required tooling installed, **When** the developer runs the single startup command, **Then** all services start successfully and the frontend is accessible within 3 minutes
2. **Given** services are running, **When** the developer sends a chat message through the frontend, **Then** a streamed response is received end-to-end
3. **Given** services are running, **When** the developer attempts to reach the backend API directly from a browser, **Then** the request is rejected — the backend is internal-only, matching production topology
4. **Given** a partially started stack (e.g., database starting slowly), **When** the backend service starts, **Then** it waits for the database to be ready before accepting traffic — no manual ordering required
5. **Given** the stack is running, **When** a developer checks service health, **Then** a single health endpoint confirms all services are ready

---

### User Story 2 — Environment Configuration Parity (Priority: P2)

A developer opens the local configuration template and sees every environment variable the deployed system requires, organized by service, with a clear distinction between variables that need real values (LLM API keys) and variables that can use safe local defaults (database URL, stub Sitecore IDs). No configuration exists in deployment that is absent from the local template.

**Why this priority**: Configuration drift between local and deployed is a leading cause of "works on my machine" bugs. Complete parity in variable documentation prevents this class of problem.

**Independent Test**: Can be fully tested by comparing the local configuration template against the deployed environment variable list for each service — every deployed variable must have a corresponding local entry with documentation.

**Acceptance Scenarios**:

1. **Given** the local configuration template, **When** compared to the deployed service variable list, **Then** every deployed variable is present in the local template with a description
2. **Given** a new environment variable is added to a deployed service, **When** the developer updates the local template, **Then** there is exactly one place to update (no duplication across services)
3. **Given** a developer who has never worked on the project, **When** they read the configuration template, **Then** they can distinguish which variables require real secret values versus safe placeholder values
4. **Given** `RUNTIME_CONTEXT=local` is set, **When** the stack starts, **Then** Sitecore OAuth and iframe context are bypassed and stub values are used — no external Sitecore connection required

---

### User Story 3 — Hot Reload for Active Development (Priority: P3)

A developer changes a line of Python in the backend service or a TypeScript component in the frontend. The change is live within seconds — no restart of the full stack required. All other services remain running and connected throughout the reload.

**Why this priority**: Slow iteration loops degrade developer productivity. Hot reload is standard practice for development environments and preserves the value of the mirrored topology during active coding.

**Independent Test**: Can be fully tested by modifying a single line in the backend (e.g., a response message) and a single line in the frontend (e.g., a UI label), then confirming each change is live within 5 seconds without running any restart command.

**Acceptance Scenarios**:

1. **Given** the full stack is running, **When** a developer saves a code change to the backend, **Then** the backend reloads and the change is active within 5 seconds
2. **Given** the full stack is running, **When** a developer saves a code change to the frontend, **Then** the browser reflects the change without a manual refresh
3. **Given** the backend reloads due to a code change, **When** the reload completes, **Then** the database connection and other service connections are re-established automatically
4. **Given** a code change introduces a syntax error, **When** the service attempts to reload, **Then** the error is shown in the terminal and the previous working version continues serving requests (or the service waits for a fix)

---

### Edge Cases

- ~~What happens when a required port is already occupied by another local process?~~ → Startup fails immediately; the error message names the blocked port and the service that needs it.
- ~~What happens when `just dev` is invoked while services are already running?~~ → Pre-flight detects occupied ports and fails immediately with named port conflicts; no duplicate services are started.
- What happens when the database volume already exists from a previous run (schema divergence)?
- ~~How does the system handle a failed database migration at startup?~~ → All services abort immediately (including any Docker containers started during this startup sequence); the full migration error output is surfaced before exit.
- ~~What happens when the developer has no LLM API key configured?~~ → Startup is refused; a clear error message identifies the missing variable by name before any service launches.
- ~~How does a developer reset to a completely clean state (including database data)?~~ → Drop and recreate all tables by re-running migrations from scratch; Docker volume is preserved.
- ~~What happens when Docker Desktop is not running?~~ → Startup fails immediately after pre-flight, before any Docker command is issued, with a message indicating Docker is unavailable.
- ~~What happens when one Docker service fails to start while another succeeds (e.g., MLflow fails, PostgreSQL succeeds)?~~ → Startup aborts; the failing service is named in the error; no partially started state is left silently running.
- ~~What happens when the database readiness wait times out?~~ → All Docker containers started in this session are stopped; a timeout error is shown with the retry count and elapsed time.
- ~~What happens when a native process (FastAPI or Next.js) crashes after successful startup?~~ → The other services continue running; the crash is visible in the shared log view with the service label; the developer must restart only the crashed service.
- ~~What happens when `alembic downgrade base` partially fails during `just reset`?~~ → The error is surfaced immediately; the schema is left in a partially downgraded state that the developer must manually recover — this is an exceptional case with no automatic rollback.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: All services MUST be startable from a single command (`just dev`) at the project root, running identically on Windows (PowerShell), macOS, and Linux. Docker manages the database and MLflow tracker; the backend API and frontend run as native processes. The startup sequence is: (1) pre-flight validation, (2) Docker infrastructure start, (3) database readiness wait, (4) database migration, (5) application service start — each step MUST complete successfully before the next begins. Pre-flight MUST run before any Docker container is started and MUST validate: (a) all required secrets are present and non-empty — the currently required secret is `LLM_API_KEY`; (b) all required ports are available — port assignments are 3000 (Next.js), 5000 (MLflow), 5432 (PostgreSQL), 8000 (FastAPI). Pre-flight failure or port conflicts MUST abort immediately with an error message naming the specific missing variable or occupied port and the service that requires it. When all services are running, a clear terminal message MUST be printed confirming the stack is available — e.g., `✓ Stack ready — http://localhost:3000`.
- **FR-002**: The developer workflow MUST route all application requests through the Next.js frontend (port 3000). No application feature or tool script MUST directly address the backend by port. This constraint is enforced by the frontend's proxy behavior, not by Docker network isolation — the backend process binds to localhost:8000 for technical reasons, but direct port access is outside the supported developer workflow.
- **FR-003**: The database MUST have all schema migrations applied automatically before the backend accepts its first request — no manual migration step after startup. If migration fails, all services MUST abort immediately — including stopping any Docker containers that were started as part of the same startup sequence — and the full migration error MUST be surfaced before exit.
- **FR-004**: The local environment MUST provide a configuration template (`.env.example` at the project root) documenting every application service variable required by the deployed system, with each variable annotated as either requiring a real secret value or accepting a safe local default. A "safe local default" is a non-secret value that allows the stack to start without any external service connection. Docker container credentials (`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`) are maintained separately in `docker/.env` and are excluded from this template.
- **FR-005**: The local configuration MUST include `RUNTIME_CONTEXT=local` to bypass Sitecore OAuth and iframe context, plus safe stub values for all Sitecore context variables (`LOCAL_PAGE_ID`, `LOCAL_SITE_ID`, `LOCAL_LANGUAGE`) so the full chat loop works without a Sitecore Cloud Portal connection
- **FR-006**: Code changes to the backend service MUST be reflected without restarting the full stack
- **FR-007**: Code changes to the frontend MUST be reflected in the browser without a manual page refresh or stack restart
- **FR-008**: The stack MUST provide a reset command that drops all tables and re-runs migrations from scratch, leaving the database empty but fully schema-current. The Docker volume and all other running services MUST remain unaffected.
- **FR-009**: The stack MUST surface a unified view of logs from all application services in a single terminal window. Each service's output MUST be prefixed with a named label (e.g., `[backend]`, `[frontend]`) so lines from different services are distinguishable at a glance. Docker infrastructure logs (PostgreSQL, MLflow) MUST be accessible separately on demand without stopping the application services.
- **FR-010**: The local MLflow tracking server MUST be accessible via a browser UI at `http://localhost:5000` so developers can inspect LLM traces during development. The MLflow version used MUST be 2.21.0 or later, as earlier versions do not support LangGraph trace autologging.

### Key Entities

- **Service configuration**: The set of environment variables, port assignments, startup parameters, and health check endpoints for each service
- **Migration state**: The current schema version applied to the local database; must match the latest migration in the codebase after every startup
- **Service topology**: The defined network relationships between services — which are accessible externally (frontend) and which are internal-only (backend API, database)
- **Local configuration template**: The single file documenting every required variable across all services, with annotations distinguishing secrets from safe defaults

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer on a clean machine can have all services running and send a successful chat request within 10 minutes of cloning the repository. This window covers full setup including dependency installation. The startup command itself (`just dev`) MUST complete within 3 minutes on a machine with dependencies already installed.
- **SC-002**: 100% of deployed environment variables are documented in the local configuration template — zero undocumented variables
- **SC-003**: A backend code change is live in the running stack within 5 seconds of saving the file
- **SC-004**: A frontend code change is reflected in the browser within 3 seconds of saving the file
- **SC-005**: The local service topology reflects the deployed topology — all application traffic routes through the Next.js frontend proxy (port 3000). The backend has no assigned public URL in the developer workflow, consistent with production where the backend has no public Railway domain. Note: the backend process binds to localhost:8000 for technical reasons; direct port access is not blocked at the network level locally, but is not part of the supported developer workflow.

## Assumptions

- Docker manages the database (PostgreSQL) and MLflow tracker only; the backend API and frontend run as native processes on the developer's machine
- Docker Desktop must be running before the startup command is invoked — the startup script does not manage the Docker daemon itself
- The local dev stack targets Windows (PowerShell), macOS, and Linux equally — no platform-specific workarounds are acceptable
- Local development uses HTTP; HTTPS is not required since Sitecore iframe OAuth is bypassed in local mode
- The LLM provider requires a real API key (`LLM_API_KEY`) — no mock or simulator is provided for the LLM itself; startup refuses without it
- The full local stack (all services) is intended for development only; individual services can still be run outside the stack for unit testing
- MLflow tracking in local mode writes to the filesystem; no remote MLflow server is required locally. MLflow 2.21.0 or later is required for LangGraph trace autologging.
- The local stack does not simulate Railway-specific infrastructure features (e.g., private networking domains like `*.railway.internal`) — service discovery uses standard localhost ports instead
- The Sitecore Marketplace SDK is unavailable in local mode; stub values from environment variables replace the iframe-injected context
- Pre-flight validation is expected to complete in under 5 seconds; failure to do so indicates an environment problem, not a feature defect
- SC-002 is verified by comparing `.env.example` against the Railway service environment variable panels for each deployed service — this comparison is performed manually at the time of each Railway deployment

## Clarifications

### Session 2026-06-17

- Q: Do the backend API and frontend run inside Docker containers, or as native processes with only the database and MLflow in Docker? → A: Docker manages DB + MLflow only; backend and frontend run as native processes
- Q: What happens at startup when the LLM API key is not configured? → A: Refuse to start; print a clear error naming the missing variable before any service launches
- Q: When a required port is already in use, what should the stack do? → A: Fail immediately with an error naming the blocked port and the service that needs it
- Q: What does "reset to clean state" (FR-008) mean? → A: Drop and recreate all tables via migrations from scratch; Docker volume and other services unaffected
- Q: When a database migration fails at startup, what happens to the rest of the stack? → A: All services abort immediately; full migration error output is surfaced before exit
