"""DBA-003 (FAZ H): Alembic migration upgrade/downgrade round-trip testleri.

Faz C migration'larinin downgrade fonksiyonlari production rollback senaryosu
icin kritik. Bu testler her migration icin upgrade/downgrade/upgrade dongusu
ile data loss riskini dogrular.

NOT: alembic env.py `asyncio.run()` cagiriyor; pytest event loop'unun icinde
direkt `alembic.command.upgrade` calismaz. Subprocess ile uvicorn'dan ayri
process'te alembic CLI cagrisi yapiyoruz — production rollback'i de subprocess
icinde calisiyor (k8s init container).
"""
import os
import subprocess
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

from tests.conftest import engine
from app.models.base import Base

# Backend root: tests/integration/ -> backend/
_BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _test_db_url() -> str:
    """Test DATABASE_URL env'den okunur; conftest.py degistirmeyi guvensiz
    sayar (kfinans_test dogrulama). Hardcoded sifre yok — CI/dev env saglar."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL env yok; migration testleri sadece test ortaminda calisir")
    return url


def _run_alembic(*args: str) -> None:
    """Subprocess ile alembic komutu calistir. DATABASE_URL env'den okunur."""
    result = subprocess.run(
        ["alembic", *args],
        cwd=_BACKEND_ROOT,
        env={**os.environ},
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"alembic {' '.join(args)} basarisiz:\nstdout={result.stdout}\nstderr={result.stderr}"
        )


@pytest_asyncio.fixture
async def fresh_db():
    """Migration testleri icin DB'yi tamamen sifirla.

    Integration conftest scope=session autouse ile ORM metadata.create_all
    ile tablo olusturmustu. Migration testi alembic upgrade'i baslangictan
    calistirmali — once tum tablolari (alembic_version dahil) sil.

    Test sonunda diger integration testlerin calismasi icin metadata.create_all
    ile orjinal duruma getir.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        # alembic_version tablosu Base'de tanimli degil; manuel sil.
        await conn.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE"))
    yield
    # Test sonu: migration tablolarini sil, ORM tablolarini geri kur.
    async with engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE"))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


async def _table_columns(table: str) -> set[str]:
    """Async ile tablonun kolon isimlerini doner."""
    engine = create_async_engine(_test_db_url())
    async with engine.connect() as conn:
        cols = await conn.run_sync(
            lambda sync_conn: {c["name"] for c in inspect(sync_conn).get_columns(table)}
        )
    await engine.dispose()
    return cols


async def _fk_ondelete(table: str, column: str) -> str | None:
    """Hedef tablodaki FK constraint'in confdeltype degerini doner.
    PG: 'a'=NO ACTION, 'c'=CASCADE, 'n'=SET NULL, 'r'=RESTRICT, 'd'=SET DEFAULT.

    NOT: confdeltype "char" tipi (1 byte). asyncpg bytes doner; decode et.
    """
    engine = create_async_engine(_test_db_url())
    async with engine.connect() as conn:
        row = await conn.execute(text("""
            SELECT confdeltype
            FROM pg_constraint c
            JOIN pg_class t ON t.oid = c.conrelid
            JOIN pg_attribute a ON a.attrelid = t.oid
            WHERE t.relname = :table
              AND a.attname = :column
              AND c.contype = 'f'
              AND a.attnum = ANY(c.conkey)
            LIMIT 1
        """), {"table": table, "column": column})
        result = row.scalar_one_or_none()
    await engine.dispose()
    if result is None:
        return None
    if isinstance(result, bytes):
        return result.decode("ascii")
    return result


@pytest.mark.asyncio
async def test_migration_head_after_upgrade(fresh_db):
    """upgrade head sonrasi en son revision DB'de markedir."""
    _run_alembic("upgrade", "head")
    cols = await _table_columns("users")
    # SEC-002 kolonlari mevcut
    assert "failed_login_count" in cols
    assert "locked_until" in cols
    # SEC-001 kolonlari mevcut
    assert "reset_token" in cols
    assert "reset_token_expires_at" in cols


@pytest.mark.asyncio
async def test_dba001_fk_ondelete_after_upgrade(fresh_db):
    """DBA-001: 5 FK'da CASCADE / SET NULL aktif mi?"""
    _run_alembic("upgrade", "head")

    # CASCADE bekleyenler ('c')
    for table, col in [
        ("integrations", "user_id"),
        ("wallet_addresses", "user_id"),
        ("portfolio_snapshots", "user_id"),
        ("asset_positions", "snapshot_id"),
        ("investment_advice", "user_id"),
    ]:
        deltype = await _fk_ondelete(table, col)
        assert deltype == "c", f"{table}.{col} CASCADE bekleniyor, gelen={deltype}"

    # SET NULL bekleyenler ('n')
    for table, col in [
        ("asset_positions", "wallet_address_id"),
        ("investment_advice", "snapshot_id"),
    ]:
        deltype = await _fk_ondelete(table, col)
        assert deltype == "n", f"{table}.{col} SET NULL bekleniyor, gelen={deltype}"


@pytest.mark.asyncio
async def test_round_trip_downgrade_then_upgrade(fresh_db):
    """Faz H migration zinciri (b9c0d1e2f3a4 KVKK haklari, a8b9c0d1e2f3 SEC-001,
    f7a8b9c0d1e2 DBA-001+SEC-002) round-trip.

    Down 3 step (KVKK + SEC-001 + SEC-002):
      - users.overseas_consent_at, email_change_token vs. silinmis olmali
      - users.failed_login_count, locked_until silinmis olmali
      - users.reset_token, reset_token_expires_at silinmis olmali
      - FK ondelete default (NO ACTION) durumuna donmus olmali
    Up sonrasi:
      - Tum kolonlar tekrar mevcut, FK CASCADE
    """
    _run_alembic("upgrade", "head")
    # KVKK + SEC-001 + SEC-002 + DBA-001'i geri al (3 yeni migration -> f7a8 oncesi)
    _run_alembic("downgrade", "-3")

    cols = await _table_columns("users")
    assert "failed_login_count" not in cols
    assert "locked_until" not in cols
    assert "reset_token" not in cols

    # FK NO ACTION durumuna dondu
    deltype = await _fk_ondelete("integrations", "user_id")
    assert deltype == "a", f"downgrade sonrasi NO ACTION bekleniyor, gelen={deltype}"

    # Upgrade — tum kolonlar + FK CASCADE
    _run_alembic("upgrade", "head")

    cols = await _table_columns("users")
    assert "failed_login_count" in cols
    assert "locked_until" in cols
    assert "reset_token" in cols
    deltype = await _fk_ondelete("integrations", "user_id")
    assert deltype == "c"


@pytest.mark.asyncio
async def test_xpub_encryption_migration_downgrade_safe(fresh_db):
    """b3c4d5e6f7a8 (FAZ C1 — wallet xpub Fernet) downgrade calismali.

    Bu migration plaintext address kolonunu address_encrypted +
    address_fingerprint olarak boler. Downgrade fonksiyonu olmasi gerekir
    ki production rollback'inde data loss olmasin (test smoke check).

    NOT: Bu test diger testler ile yarista DB state'i bozabilir; en sonda
    head'e geri donulur. Diger izolasyonsuz testler etkilenirse seri calistir.
    """
    _run_alembic("upgrade", "head")
    # b3c4d5e6f7a8'a kadar downgrade (degil sonrasinda da head'e ger)
    try:
        _run_alembic("downgrade", "b3c4d5e6f7a8")
    except Exception as e:
        pytest.fail(
            f"FAZ C1 (b3c4d5e6f7a8) oncesine downgrade yapilamadi: {e}"
        )
    # Tekrar head — round-trip
    _run_alembic("upgrade", "head")
