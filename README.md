# Multimodal Marketing App

A Sitecore XM Cloud Pages sidebar extension that provides an AI-powered marketing assistant. The assistant helps marketers write content, audit pages, plan campaigns, and optimize for SEO — all without leaving the editor.

## Architecture

| Layer | Technology | Port |
|-------|------------|------|
| Frontend | Next.js 15 (App Router, TypeScript) | 3000 |
| Backend | Python / FastAPI | 8000 |
| Database | PostgreSQL (Docker) | 5432 |
| Observability | MLflow | 5000 |

## Prerequisites

- [Python 3.12+](https://www.python.org/downloads/)
- [Node.js 20+](https://nodejs.org/)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- [just](https://github.com/casey/just) — task runner (`winget install casey.just` on Windows)
- An OpenAI API key (or compatible provider)

## Project Layout Note

This is a monorepo with a Python/FastAPI backend (`backend/`) and a Next.js frontend (`frontend/`). Environment variables live in a single root `.env` file. The backend reads it directly; Next.js cannot look outside its own directory, so `just dev` generates `frontend/.env.local` from the root file automatically. **Always use `just dev` rather than running `npm run dev` directly** to ensure the frontend has current env vars.

## Quick Start

```powershell
# 1. Copy and fill in the environment file
cp .env.example .env
# Edit .env — at minimum set LLM_API_KEY

# 2. Install Python dependencies (first time only)
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
cd ..

# 3. Install frontend dependencies (first time only)
cd frontend
npm install
cd ..

# 4. Start everything (Docker DB + migrations + backend + frontend)
just dev
```

The app runs at `http://localhost:3000`. FastAPI docs: `http://localhost:8000/docs`.

## Environment Variables

Copy `.env.example` to `.env` and fill in the required values:

| Variable | Required | Description |
|----------|----------|-------------|
| `LLM_API_KEY` | **Yes** | OpenAI API key (or compatible provider) |
| `LLM_MODEL` | No | Defaults to `gpt-4o-mini` |
| `DATABASE_URL` | No | Defaults to local Docker Postgres |
| `RUNTIME_CONTEXT` | No | `local` (default) or `iframe` |
| `MLFLOW_TRACKING_URI` | No | Defaults to `http://localhost:5000` |

## Development Commands

```powershell
just dev       # Start full stack (Docker + backend + frontend)
just stop      # Stop Docker containers
just reset     # Drop and recreate DB tables
just logs      # Stream Docker logs
```

## Validation

See [specs/001-core-chat-app/quickstart.md](specs/001-core-chat-app/quickstart.md) for full end-to-end validation scenarios covering:

- US1: Streaming chat loop
- US2: Sitecore OAuth authentication (requires iframe context)
- US3: Local development mode

## Project Structure

```
├── backend/                # FastAPI application
│   ├── app/
│   │   ├── api/            # Route handlers (chat, conversations, auth)
│   │   ├── clients/        # LLM, tools, auth verifier
│   │   ├── resources/      # DB engine, models, schemas
│   │   └── services/       # Chat graph, instruction loader, guardrails
│   ├── alembic/            # DB migrations
│   └── instructions/       # System prompt, guardrails, task overlays
├── frontend/               # Next.js application
│   ├── app/                # App Router pages and API proxy routes
│   ├── components/         # ChatPanel, MessageBubble, AuthGate, etc.
│   └── lib/                # Hooks (useChat, useSitecoreContext), types
└── docker/                 # Docker Compose for local infrastructure
```
