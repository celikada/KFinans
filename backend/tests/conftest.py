import os
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool
from app.main import app
from app.core.deps import get_db
from app.core.limiter import limiter
from app.models.base import Base

TEST_DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://kfinans:kfinans_test@localhost:5432/kfinans_test",
)

# Test ortaminda slowapi rate limiter devre disi — testler arasi 429 patlamalarini onler
limiter.enabled = False

# NullPool: her connection sonrasi kapanir; pytest-asyncio'nun event loop
# yeniden olusturmasi nedeniyle olusan "different loop" hatalarini onler.
engine = create_async_engine(TEST_DB_URL, echo=False, poolclass=NullPool)
TestSession = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def db():
    """Tek HTTP istegi yapan testler icin tekil session."""
    async with TestSession() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client():
    """Her istek icin ayri session uretir — eszamanli istek cakismasini onler."""
    async def _override():
        async with TestSession() as session:
            yield session

    app.dependency_overrides[get_db] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
