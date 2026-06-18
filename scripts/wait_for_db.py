#!/usr/bin/env python3
"""Poll PostgreSQL until it accepts connections, with exponential backoff."""

import os
import sys

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

load_dotenv()


@retry(
    stop=stop_after_attempt(30),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def _connect(url: str) -> None:
    engine = create_engine(url, connect_args={"connect_timeout": 5})
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    engine.dispose()


def main() -> None:
    raw_url = os.environ.get("DATABASE_URL", "").strip()
    if not raw_url:
        print("ERROR: DATABASE_URL is not set", file=sys.stderr)
        sys.exit(1)

    url = raw_url.replace("postgresql+asyncpg://", "postgresql://", 1).strip()
    print("Waiting for database...")
    try:
        _connect(url)
        print("Database ready")
    except Exception as exc:
        print(f"ERROR: Could not connect to PostgreSQL after 30 attempts: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
