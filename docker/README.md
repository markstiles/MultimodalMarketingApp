# Docker Infrastructure

This folder contains the Docker configuration for the local development infrastructure: PostgreSQL (Supabase-flavored) and the MLflow tracking server.

**This folder integrates with `just dev` at the project root.** You do not need to run `docker compose` directly for normal development — use `just dev` to start the full stack, `just stop` to stop containers, and `just logs` to stream Docker infra logs.

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop) (Windows/Mac/Linux)
- [`just`](https://github.com/casey/just) task runner (`winget install just` on Windows; `brew install just` on macOS)

## Quick Start (Recommended)

From the project root:

```bash
# Copy and fill in secrets
cp .env.example .env         # root app config — fill in LLM_API_KEY
cp docker/.env.example docker/.env  # Docker credentials — defaults work for local dev

# Start the full stack (runs preflight, Docker, migrations, and app processes)
just dev
```

## Manual Docker Usage

If you need to manage Docker containers directly (outside `just dev`):

```bash
# Start containers
docker compose -f docker/docker-compose.yml up -d

# Stop containers
docker compose -f docker/docker-compose.yml stop

# Stream logs
docker compose -f docker/docker-compose.yml logs -f

# Connect to PostgreSQL
docker exec -it postgres psql -U postgres -d marketing_app
```

## Services

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| postgres | `supabase/postgres:17.6.1.067` | 5432 | PostgreSQL with extensions (PostGIS, pgvector, etc.) |
| mlflow | `ghcr.io/mlflow/mlflow:v2.19.0` | 5000 | LLM trace tracking — UI at http://localhost:5000 |

## Configuration

Credentials are read from `docker/.env` (gitignored). Copy `docker/.env.example` to `docker/.env` — the defaults work for local development:

```env
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=marketing_app
```

These values must match the `DATABASE_URL` in the root `.env` file. The default `DATABASE_URL` in `.env.example` already matches.

## File Structure

```
docker/
├── docker-compose.yml      # PostgreSQL + MLflow service definitions
├── .env.example            # Docker credential template (KEY=value format)
├── .env                    # Actual credentials (gitignored — copy from .env.example)
├── README.md               # This file
├── certs/                  # SSL certificates (if applicable)
├── generate-certs.ps1      # Certificate generation script
└── data/                   # Persistent volume data (gitignored)
    ├── pgdata/             # PostgreSQL data files
    └── mlflow/             # MLflow SQLite DB and artifacts
```

## Troubleshooting

### "Connection refused" on localhost:5432

1. Verify containers are running: `docker compose -f docker/docker-compose.yml ps`
2. Check logs: `just logs`
3. Ensure port 5432 is not in use by another process

### "Password authentication failed"

1. Confirm `docker/.env` exists (copy from `docker/.env.example`)
2. Confirm `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` in `docker/.env` match the credentials in `DATABASE_URL` in the root `.env`
3. Restart containers: `docker compose -f docker/docker-compose.yml stop && docker compose -f docker/docker-compose.yml up -d`

### Reset Database

To drop and recreate all tables (preserves Docker volume):

```bash
just reset
```

This runs `alembic downgrade base && alembic upgrade head` — all data is deleted but the Docker volume and other services remain running.

This Docker setup is **for local development only**.
