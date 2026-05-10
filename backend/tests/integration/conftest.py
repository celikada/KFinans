import pytest_asyncio
from sqlalchemy import text

from tests.conftest import engine
from app.models.base import Base


@pytest_asyncio.fixture(scope="session", autouse=True)
async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# TEST-004 (FAZ H): Function-scoped TRUNCATE — her test sonrasi DB sifirlanir.
# Onceki davranis: client fixture session-per-request commit'i gerceklestiriyordu;
# rollback olmadigi icin testler kumulatif (DB state leak). pytest-xdist paralel
# kosumda flaky.
#
# Cozum: TRUNCATE ... RESTART IDENTITY CASCADE her test sonunda. Schema (DDL)
# korunur — her test schema cleaning maliyeti odemez. Tahmini maliyet ~100ms/test
# (305 test = 30sn ekstra).
#
# Migration testleri (test_migrations.py) kendi fresh_db fixture'i ile drop_all +
# alembic upgrade yapar; bu autouse fixture once calisir + migration testleri
# kendi setup'ini yapar — cakisma yok.

# Tablolar Base.metadata.tables'tan dinamik alinir (yeni tablo eklendiğinde
# liste guncellemeye gerek yok). alembic_version dahil edilmez (migration
# testleri haric, schema kalir).
_TRUNCATE_EXCLUDE = {"alembic_version"}


@pytest_asyncio.fixture(autouse=True)
async def _truncate_after_test():
    yield
    table_names = [
        t.name for t in Base.metadata.sorted_tables
        if t.name not in _TRUNCATE_EXCLUDE
    ]
    if not table_names:
        return
    async with engine.begin() as conn:
        # CASCADE FK iliski'leri otomatik halleder; RESTART IDENTITY auto-increment
        # PK'lari sifirlar (testler arasi ID baski tutarli).
        joined = ", ".join(table_names)
        await conn.execute(text(f"TRUNCATE TABLE {joined} RESTART IDENTITY CASCADE"))
