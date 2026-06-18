import os
from typing import Optional

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

load_dotenv()

_engine = None
_session_factory = None


def _get_db_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif not url.startswith("postgresql+asyncpg://"):
        raise ValueError(f"Unsupported DATABASE_URL scheme: {url[:30]}")
    return url


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            _get_db_url(),
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=3600,
        )
    return _engine


def _get_session_factory():
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(_get_engine(), expire_on_commit=False)
    return _session_factory


async def get_db() -> AsyncSession:
    async with _get_session_factory()() as session:
        yield session
