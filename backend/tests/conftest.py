import os
import sys
from pathlib import Path

# Make the backend package importable from tests/
sys.path.insert(0, str(Path(__file__).parent.parent))

# Set required env vars before any app import
os.environ.setdefault("RUNTIME_CONTEXT", "local")
os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres")
os.environ.setdefault("LLM_API_KEY", "test-key")
os.environ.setdefault("LLM_MODEL", "gpt-4o-mini")
