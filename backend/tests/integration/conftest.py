"""
Shared fixtures for backend integration tests.

Uses a synchronous SQLite test engine wrapped in an async-compatible session
adapter so integration tests can run even when aiosqlite is unavailable.
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.db.models import Base
from backend.app.db.session import get_db
from backend.app.main import app


class AsyncSessionShim:
    """
    Minimal async facade over a sync SQLAlchemy Session.
    Covers all methods used by current API code and integration tests.
    """

    def __init__(self, session: Session):
        self._session = session

    def __getattr__(self, name):
        return getattr(self._session, name)

    async def execute(self, *args, **kwargs):
        return self._session.execute(*args, **kwargs)

    async def flush(self, *args, **kwargs):
        self._session.flush(*args, **kwargs)

    async def commit(self):
        self._session.commit()

    async def rollback(self):
        self._session.rollback()

    async def close(self):
        self._session.close()


# ── Shared in-memory SQLite DB for tests ──────────────────────────────────────
engine = create_engine(
    "sqlite://",
    echo=False,
    future=True,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
SyncSessionFactory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


async def override_get_db():
    """Override FastAPI's get_db to use the integration test SQLite database."""
    sync_session = SyncSessionFactory()
    session = AsyncSessionShim(sync_session)
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


# Wire the override into the FastAPI app
app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    """Create all tables before each test, drop after."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest_asyncio.fixture
async def client():
    """Async httpx test client for FastAPI integration tests."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient) -> dict:
    """Register a test user and return auth headers."""
    resp = await client.post(
        "/api/auth/register",
        json={
            "email": "test@debate.com",
            "password": "testpass123",
            "name": "Test User",
        },
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def db_session():
    """Direct DB session for setting up test data."""
    sync_session = SyncSessionFactory()
    session = AsyncSessionShim(sync_session)
    try:
        yield session
        await session.commit()
    finally:
        await session.close()
