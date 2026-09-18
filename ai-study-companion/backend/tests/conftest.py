"""Pytest configuration and shared fixtures."""
import socket
import pytest
import pytest_asyncio
from app.db.session import engine


def is_postgres_available() -> bool:
    """Check if Postgres server is reachable."""
    for host in ("db", "127.0.0.1", "localhost"):
        try:
            with socket.create_connection((host, 5432), timeout=0.2):
                return True
        except OSError:
            continue
    return False


@pytest_asyncio.fixture(autouse=True)
async def cleanup_db_connections():
    """Ensure DB connection pool is cleanly disposed between test runs."""
    yield
    try:
        await engine.dispose()
    except Exception:
        pass
