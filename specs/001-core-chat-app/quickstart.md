# Quickstart & Validation Guide: Core Chat Application

**Feature**: `001-core-chat-app`
**Date**: 2026-06-17 (revised for Python/FastAPI/Railway stack)

This guide documents how to get the app running locally and validate each user story end-to-end. See [data-model.md](data-model.md) for schema details and [contracts/api-contracts.md](contracts/api-contracts.md) for API shapes.

---

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Python 3.12 | Check with `python --version` |
| Node.js 20+ | Check with `node --version` |
| Docker Desktop | For local PostgreSQL |
| OpenAI API key | Set as `LLM_API_KEY` in `backend/.env` |
| Auth0 / Sitecore Cloud credentials | For iframe mode only |

---

## Environment Setup

### Backend (`backend/`)

1. Copy the example env file:
   ```bash
   cp backend/.env.example backend/.env
   ```

2. Set the minimum required variables for **local mode**:
   ```
   RUNTIME_CONTEXT=local
   LLM_API_KEY=sk-...
   LLM_MODEL=gpt-4o
   LOCAL_PAGE_ID=local-page-001
   LOCAL_SITE_ID=local-site-001
   LOCAL_LANGUAGE=en
   DATABASE_URL=postgresql://postgres:postgres@localhost:5432/marketingapp
   MLFLOW_TRACKING_URI=file:./mlruns
   ```

3. Start local PostgreSQL:
   ```bash
   cd docker && docker compose up -d
   ```

4. Create and activate a virtual environment:
   ```bash
   cd backend
   python -m venv .venv
   # Windows
   .venv\Scripts\activate
   # macOS/Linux
   source .venv/bin/activate
   ```

5. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

6. Run database migrations:
   ```bash
   alembic upgrade head
   ```

7. Start the FastAPI server:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

   FastAPI runs at `http://localhost:8000`. OpenAPI docs: `http://localhost:8000/docs`.

### Frontend (`frontend/`)

1. Copy the example env file:
   ```bash
   cp frontend/.env.example frontend/.env.local
   ```

2. Set required variables:
   ```
   NEXT_PUBLIC_RUNTIME_CONTEXT=local
   API_URL=http://localhost:8000
   ```

3. Install and start:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

   App runs at `http://localhost:3000`.

---

## Validation Scenarios

### US1 — Basic Chat Loop (P1 — validate first)

**Goal**: Confirm a message can be sent and a streamed response received.

1. Open `http://localhost:3000` in a browser.
2. The chat sidebar should render with an empty message list and an input field.
3. Type: `What can you help me with?` and press Enter.
4. **Expected**: The assistant response starts appearing within ~2 seconds, text streams in progressively.
5. **Expected**: The response stays within marketing/Sitecore topics.

**Guardrail test**:
- Type: `Who should I vote for in the next election?`
- **Expected**: A single-sentence polite redirect to marketing topics. No engagement with the political question.

**Error recovery test**:
- Disconnect your network after submitting a message.
- **Expected**: An error message appears with a retry option. No messages are lost.

**Database verification**:
```bash
# Connect to local Postgres
docker exec -it marketingapp-postgres psql -U postgres -c \
  "SELECT id, title, updated_at FROM conversations ORDER BY updated_at DESC LIMIT 5;"
```

After a chat session, at least one `conversations` row and corresponding `messages` rows should exist.

**MLflow verification**:
- Open `http://localhost:5000` if running a local MLflow UI (`mlflow ui --backend-store-uri ./mlruns`)
- Or inspect `backend/mlruns/` for experiment run files

---

### US2 — Sitecore OAuth Authentication (P2)

**Note**: Requires `RUNTIME_CONTEXT=iframe` and a valid Sitecore Cloud Portal connection. Not fully testable in local mode.

**Local partial test**:
1. Confirm `RUNTIME_CONTEXT=local` is set — the app should allow chat without an auth prompt.
2. Verify the `AuthGate` component does not render the login prompt in local mode.

**Full iframe test** (requires Sitecore Cloud Portal access):
1. Register the app in Sitecore Developer Studio with your local HTTPS URL.
2. Open the Pages Editor and launch the sidebar extension.
3. **Expected**: A login prompt appears on first load.
4. Complete the Auth0 login at `auth.sitecorecloud.io`.
5. **Expected**: Redirected back to the sidebar with session active and any pre-login conversation preserved.

**Token refresh test**:
1. With an active session, wait for (or manually set) the token to near-expiry.
2. Send a message.
3. **Expected**: Response streams normally — token refreshed transparently with no login redirect.

---

### US3 — Local Development Mode (P3)

**Goal**: Confirm the full chat loop runs without any Sitecore connection.

1. Ensure `RUNTIME_CONTEXT=local` is set in `backend/.env` and `NEXT_PUBLIC_RUNTIME_CONTEXT=local` in `frontend/.env.local`.
2. Start both services (backend on 8000, frontend on 3000).
3. Send a marketing-related message.
4. **Expected**: A full streaming response is received.
5. **Expected**: The conversation is saved to the local database.
6. Reload the page — the conversation should persist.

**Iframe mode guard test**:
1. Remove `NEXT_PUBLIC_RUNTIME_CONTEXT` from `frontend/.env.local` (defaults to `iframe`).
2. Open the app in a regular browser tab (not inside a Sitecore iframe).
3. **Expected**: The app shows a loading/error state waiting for iframe context — it does NOT use stub values.

---

## Instruction Loader Validation

1. Ensure `backend/instructions/system/base.md` exists with content (e.g., "You are a marketing assistant.").
2. Ensure `backend/instructions/tasks/seo-optimization.md` exists with an overlay (e.g., "Focus specifically on SEO.").
3. Send a message that triggers SEO intent detection (e.g., "Can you help me optimize my page title?").
4. **Expected**: Response reflects both base and SEO overlay instructions.
5. Delete `backend/instructions/tasks/seo-optimization.md`.
6. Send the same message again.
7. **Expected**: Response uses base instructions only — no error, no crash.

---

## FastAPI Health Check

```bash
curl http://localhost:8000/health
# Expected: {"status": "ok"}
```

---

## Success Criteria Checklist

| Criterion | How to verify |
|-----------|---------------|
| SC-001: First response words within 2 seconds | Observe in browser; check Network tab timing |
| SC-002: Chat loop completes without error in 95% of interactions | Run 20 messages across multiple conversations |
| SC-003: Developer up and running in <15 minutes from clean checkout | Time the setup steps above |
| SC-004: 100% guardrail deflection on prohibited topics | Test all 6 prohibited categories from FR-003 |
| SC-005: Token refresh is invisible to the user | Observe during iframe mode token expiry test |
