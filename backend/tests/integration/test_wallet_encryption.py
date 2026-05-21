"""
Wallet address Fernet sifreleme regresyon testleri.

Bu testler kritik bir guvenlik invariantini koruyor:
  - DB'deki wallet_addresses.address_encrypted ASLA plaintext icermez
  - ORM'den okunan wallet.address her zaman decrypt edilmis plaintext'tir
  - Aynı address farkli case ile girilirse fingerprint ayni cikip duplicate
    onlenir (EVM checksum varyasyonlari)
  - IDOR korumalari (user_id filtresi) bozulmaz

Mevcut test_wallets_api.py UI seviyesinde (encrypted oldugunu fark etmeden)
calisirsa, bu dosya DB seviyesinde gercek sifrelemeyi dogrular.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.core.security import address_fingerprint, decrypt_secret
from tests.conftest import TestSession, make_user

VALID_BTC_XPUB = "xpub6CUGRUonZSQ4TWtTMmzXdrXDtypWKiKrhko4egpiMZbpiaQL2jkwSB1icqYh2cfDfVxdx4df189oLKnC5fSwqPfgyP3hooxujYzAu3fDVmz"
VALID_ETH_LOWER = "0x1234567890123456789012345678901234567890"
VALID_ETH_CHECKSUM = (
    "0x1234567890123456789012345678901234567890"  # checksum varies; lowercase normalize ile aynidir
)


@pytest.mark.asyncio
async def test_db_stores_only_ciphertext_no_plaintext(client: AsyncClient):
    """Kritik: DB'de plaintext address ASLA bulunmamali."""
    headers = await make_user(client, "wallet_enc_db@example.com")
    resp = await client.post(
        "/api/v1/wallets",
        json={"chain": "bitcoin", "address": VALID_BTC_XPUB, "label": "BTC xpub"},
        headers=headers,
    )
    assert resp.status_code in (200, 201)

    # Raw SQL ile DB'yi oku — ORM otomatik decrypt'i bypass ediyoruz.
    async with TestSession() as session:
        rows = (
            await session.execute(
                text("SELECT address_encrypted, address_fingerprint FROM wallet_addresses")
            )
        ).fetchall()

    assert any(rows), "wallet kaydi olusmali"
    for encrypted, fp in rows:
        # Ciphertext plaintext degildir
        assert encrypted != VALID_BTC_XPUB, "DB'de plaintext xpub bulundu — guvenlik ihlali!"
        # Ciphertext Fernet formatindadir (base64-url-safe, gAAA... ile baslar)
        assert encrypted.startswith("gAAAAA"), (
            f"Fernet ciphertext beklendi, geldi: {encrypted[:20]}"
        )
        # Fingerprint hex 64 karakter (SHA-256)
        assert len(fp) == 64
        assert all(c in "0123456789abcdef" for c in fp)


@pytest.mark.asyncio
async def test_orm_returns_decrypted_plaintext(client: AsyncClient):
    """ORM uzerinden okunan address her zaman plaintext olmali (transparent decrypt).

    BACK-013 (FAZ H) sonrasi: API JSON response'ta address MASKELI doner
    (xpub leak engeli). Bu test iki katmani ayri ayri dogrular:
      1. Python ORM seviyesinde wallet.address full plaintext (ic kullanim icin)
      2. HTTP JSON response'ta mask edilmis (ilk 6 + son 4) — ic ile dis
         kontrolu farkli.
    """
    from sqlalchemy import select

    from app.models.integration import WalletAddress

    headers = await make_user(client, "wallet_enc_orm@example.com")
    add_resp = await client.post(
        "/api/v1/wallets",
        json={"chain": "ethereum", "address": VALID_ETH_LOWER},
        headers=headers,
    )
    assert add_resp.status_code in (200, 201)

    # 1) ORM seviyesi: hybrid_property otomatik decrypt
    # NOT: Diger testlerden birikmis ethereum wallet'lari olabilir (test izolasyonu
    # yok — TEST-004 ayri issue). Sadece bu testin user'ina ait wallet'i ara.
    from app.models.user import User

    async with TestSession() as session:
        user = (
            await session.execute(select(User).where(User.email == "wallet_enc_orm@example.com"))
        ).scalar_one()
        wallet = (
            await session.execute(
                select(WalletAddress).where(
                    WalletAddress.user_id == user.id,
                    WalletAddress.chain == "ethereum",
                )
            )
        ).scalar_one()
        assert wallet.address == VALID_ETH_LOWER

    # 2) API seviyesi (BACK-013): JSON response'ta address masked
    list_resp = await client.get("/api/v1/wallets", headers=headers)
    assert list_resp.status_code == 200
    wallets = list_resp.json()
    assert len(wallets) == 1
    assert wallets[0]["address"] != VALID_ETH_LOWER, "API plaintext xpub leak — BACK-013 ihlali"
    assert "..." in wallets[0]["address"]  # mask formati: ilk 6 + ... + son 4
    assert wallets[0]["address"].startswith(VALID_ETH_LOWER[:6])
    assert wallets[0]["address"].endswith(VALID_ETH_LOWER[-4:])


@pytest.mark.asyncio
async def test_fingerprint_round_trip_helper():
    """address_fingerprint deterministic + lowercase normalize edilmis."""
    fp_lower = address_fingerprint("0xabcdef0000000000000000000000000000000000")
    fp_upper = address_fingerprint("0xABCDEF0000000000000000000000000000000000")
    fp_mixed = address_fingerprint("0xAbCdEf0000000000000000000000000000000000")
    assert fp_lower == fp_upper == fp_mixed, "EVM checksum farkliliklari ayni fingerprint vermeli"


@pytest.mark.asyncio
async def test_decrypt_round_trip_via_helper():
    """encrypt + decrypt round-trip dogrulamasi."""
    from app.core.security import encrypt_secret

    plaintext = VALID_BTC_XPUB
    ciphertext = encrypt_secret(plaintext)
    assert ciphertext != plaintext
    assert decrypt_secret(ciphertext) == plaintext


@pytest.mark.asyncio
async def test_uniqueness_via_fingerprint_blocks_case_variants(client: AsyncClient):
    """Ayni address farkli case ile ikinci kez eklenirse 409 dönmeli."""
    headers = await make_user(client, "wallet_enc_unique@example.com")
    eth_lower = "0xaaaa000000000000000000000000000000000099"
    eth_upper = "0xAAAA000000000000000000000000000000000099"

    r1 = await client.post(
        "/api/v1/wallets",
        json={"chain": "ethereum", "address": eth_lower},
        headers=headers,
    )
    assert r1.status_code in (200, 201)

    r2 = await client.post(
        "/api/v1/wallets",
        json={"chain": "ethereum", "address": eth_upper},
        headers=headers,
    )
    assert r2.status_code == 409, "Ayni address farkli case ile duplicate olmamali"


@pytest.mark.asyncio
async def test_idor_unchanged_after_encryption(client: AsyncClient):
    """User A'nin wallet'i User B icin gorunmemeli (mevcut IDOR davranisi korunsun)."""
    user_a = await make_user(client, "idor_a@example.com")
    user_b = await make_user(client, "idor_b@example.com")

    await client.post(
        "/api/v1/wallets",
        json={"chain": "bitcoin", "address": VALID_BTC_XPUB},
        headers=user_a,
    )

    list_b = await client.get("/api/v1/wallets", headers=user_b)
    assert list_b.status_code == 200
    assert list_b.json() == [], "B, A'nin wallet'ini gormemeli"


@pytest.mark.asyncio
async def test_fernet_key_change_makes_old_ciphertext_unreadable():
    """FERNET_KEY rotasyonu prosedurunun gerekliligini gosterir.

    Bu test sifrelemenin reversible-with-key oldugunu, key olmadan/yanlis
    key ile decrypt'in fail ettigini dogrular. Production'da key rotasyonu
    icin dual-decrypt + re-encrypt prosedurune ihtiyac vardir (docs/07-guvenlik.md
    section 5.3).
    """
    from cryptography.fernet import Fernet, InvalidToken

    from app.core.security import encrypt_secret

    ciphertext = encrypt_secret(VALID_BTC_XPUB)

    # Farkli key ile decrypt deneme
    other_fernet = Fernet(Fernet.generate_key())
    with pytest.raises(InvalidToken):
        other_fernet.decrypt(ciphertext.encode())
