set windows-shell := ["pwsh.exe", "-NoLogo", "-Command"]

export PYTHONUTF8 := "1"

python  := if os_family() == "windows" { "./backend/.venv/Scripts/python.exe" } else { "backend/.venv/bin/python" }
alembic := if os_family() == "windows" { "./backend/.venv/Scripts/alembic.exe" } else { "backend/.venv/bin/alembic" }

# List available recipes
default:
    @just --list

# Start the full local stack (infrastructure + application services)
dev:
    just stop
    {{python}} scripts/preflight.py
    {{python}} scripts/gen_frontend_env.py
    docker compose -f docker/docker-compose.yml up -d
    {{python}} scripts/wait_for_db.py
    {{alembic}} -c backend/alembic.ini upgrade head
    {{python}} scripts/start_dev.py

# Stop Docker containers and free ports 3000/8000 left by honcho child processes
stop:
    docker compose -f docker/docker-compose.yml stop
    -Get-NetTCPConnection -LocalPort 3000,8000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }

# Drop and recreate all DB tables from scratch (Docker volume preserved)
reset:
    {{alembic}} -c backend/alembic.ini downgrade base && {{alembic}} -c backend/alembic.ini upgrade head

# Stream Docker infra logs (PostgreSQL + MLflow)
logs:
    docker compose -f docker/docker-compose.yml logs -f

# Run unit tests (no live stack needed)
test-unit:
    {{python}} -m pytest backend/tests/ -v

# Run end-to-end smoke tests against the live stack (requires `just dev` to be running)
test:
    {{python}} scripts/smoke_test.py
