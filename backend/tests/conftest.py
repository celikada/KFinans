import os
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.deps import get_db
from app.core.limiter import limiter
from app.main import app
from app.models.user import User

TEST_DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://kfinans:kfinans_test@localhost:5432/kfinans_test",
)

# GUVENLIK: Production DB'ye yanlislikla baglanmamak icin sert kontrol.
# integration/conftest.py icindeki create_tables fixture'i drop_all yapiyor;
# yanlis bir DATABASE_URL ile testler ana DB'yi siler.
if TEST_DB_URL.endswith("/kfinans") or TEST_DB_URL.endswith("/kfinans/"):
    raise RuntimeError(f"Testler 'kfinans' veritabanina baglanamaz — bu DB drop_all ile silinir. Mutlaka 'kfinans_test' kullanin. Mevcut: {TEST_DB_URL}")

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


@pytest.fixture(autouse=True)
def _disable_password_policy_by_default(request, monkeypatch):
    """SEC (audit #5): zxcvbn + HIBP policy testleri kirmasin diye varsayilan
    olarak bypass. Mevcut 50+ test "guclu-sifre-123" gibi sifrelerle calisiyor;
    bunlar zxcvbn'i gecebilir ama HIBP icin network call yapilir.

    Policy'yi test eden testler `password_policy_enabled` marker'i kullanir:

        @pytest.mark.password_policy_enabled
        async def test_weak_password_rejected(client):
            ...

    Bypass: register/change-password/reset-password endpoint'lerinin import
    ettigi sembolleri monkey-patch ediyoruz.
    """
    if request.node.get_closest_marker("password_policy_enabled"):
        # Gercek policy aktif — test kendisi respx ile HIBP mock'lar
        # (hibp_check_enabled'a dokunma; aksi halde endpoint early-return 0
        # ile mock'lar bypass edilir).
        yield
        return

    async def _hibp_noop(*_args, **_kwargs) -> int:
        return 0

    def _strength_noop(*_args, **_kwargs) -> tuple[bool, str]:
        return True, ""

    # auth.py ve user.py modullerinin import ettikleri sembolleri patch et
    monkeypatch.setattr("app.api.v1.auth.check_password_strength", _strength_noop)
    monkeypatch.setattr("app.api.v1.auth.check_hibp_pwned", _hibp_noop)
    monkeypatch.setattr("app.api.v1.user.check_password_strength", _strength_noop)
    monkeypatch.setattr("app.api.v1.user.check_hibp_pwned", _hibp_noop)
    yield


async def verify_user_email(email: str) -> None:
    """Test yardimcisi: kayit sonrasi e-posta dogrulamasini DB uzerinden simule et.

    Test ortaminda gercek e-posta gonderimi yok; bu helper login'in calisabilmesi
    icin email_verified=True yapip verify_token'i temizler.
    """
    async with TestSession() as session:
        await session.execute(
            update(User)
            .where(User.email == email)
            .values(
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
