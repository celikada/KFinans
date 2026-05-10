import os
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import update
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool
from app.main import app
from app.core.deps import get_db
from app.core.limiter import limiter
from app.models.base import Base
from app.models.user import User

TEST_DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://kfinans:kfinans_test@localhost:5432/kfinans_test",
)

# GUVENLIK: Production DB'ye yanlislikla baglanmamak icin sert kontrol.
# integration/conftest.py icindeki create_tables fixture'i drop_all yapiyor;
# yanlis bir DATABASE_URL ile testler ana DB'yi siler.
if TEST_DB_URL.endswith("/kfinans") or TEST_DB_URL.endswith("/kfinans/"):
    raise RuntimeError(
        f"Testler 'kfinans' veritabanina baglanamaz — bu DB drop_all ile silinir. "
        f"Mutlaka 'kfinans_test' kullanin. Mevcut: {TEST_DB_URL}"
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


@pytest.fixture(autouse=True)
def _reset_tcmb_cache():
    """FIN-007 (FAZ H): TCMB rates modul-level cache (300s TTL) testler arasi
    paylasildigindan respx mock degisiklikleri etkisiz kaliyordu. Her test
    oncesi cache sifirla — testler izole.
    """
    from app.services import aggregator
    aggregator._tcmb_cache = None
    yield


async def verify_user_email(email: str) -> None:
    """Test yardimcisi: kayit sonrasi e-posta dogrulamasini DB uzerinden simule et.

    Test ortaminda gercek e-posta gonderimi yok; bu helper login'in calisabilmesi
    icin email_verified=True yapip verify_token'i temizler.
    """
    async with TestSession() as session:
        await session.execute(
            update(User).where(User.email == email).values(
                email_verified=True,
                verify_token=None,
                verify_token_expires_at=None,
            )
        )
        await session.commit()


async def make_user(client: AsyncClient, email: str | None = None) -> dict:
    """TEST-002 (FAZ H): Tum integration testleri icin tek auth helper.

    Onceki durum: 18 test dosyasinin her birinde ayni 6-satirlik `_make_user`
    helper'i kopyalanmisti. Artik conftest'ten import edilir.

    Kullanim:
        headers = await make_user(client, "ozel@example.com")  # belirli email
        headers = await make_user(client)                       # uuid auto

    Doner: dict {"Authorization": "Bearer <access_token>"}
    """
    if email is None:
        email = f"u-{uuid.uuid4().hex[:12]}@example.com"
    pwd = "guclu-sifre-123"
    # COMP-010 (FAZ H): age_confirmed zorunlu — testler default True gonderir.
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": pwd, "age_confirmed": True},
    )
    await verify_user_email(email)
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": pwd})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}
