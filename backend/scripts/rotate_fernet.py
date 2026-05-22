"""SEC-012: Tüm Fernet-encrypted column'ları primary key ile yeniden encrypt et.

MultiFernet `rotate(token)` token'ı secondary key'lerle decrypt ettikten sonra
primary key ile yeniden encrypt eder. Bu script tüm encrypted alanları gezer
ve rotate uygular — tamamlandıktan sonra `FERNET_KEYS_SECONDARY` env'i
güvenle boşaltılabilir.

Kullanım:
    cd backend
    py -m scripts.rotate_fernet              # gerçek rotate + commit
    py -m scripts.rotate_fernet --dry-run    # decrypt başarılı mı kontrol; DB'ye yazma yok
    py -m scripts.rotate_fernet --batch-size 50  # default 100

Önkoşullar:
    - `FERNET_KEY` env'i YENİ primary key (yeni encrypt'ler bununla yapılır)
    - `FERNET_KEYS_SECONDARY` env'i ESKİ primary'yi içerir (ör. `["<eski-key>"]`)
    - DATABASE_URL erişimi
    - Backend pod'lar tercihen down (atomik rotate; concurrent write yarış riski)
      veya read-only mode

Etkilenen tablolar:
    - wallet_addresses.address_encrypted
    - integrations.encrypted_key, integrations.encrypted_secret
    - users.totp_secret (NULL olabilir, sadece set olanlar)

Hata davranışı:
    InvalidToken (decrypt başarısız) — row atlanır, log'a yazılır. Bu durumda
    o satırın eski primary key'i artık `FERNET_KEYS_SECONDARY`'de yok demektir.
    Script tüm satırları tarayıp en sonda toplam başarı/hata raporu verir.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from cryptography.fernet import InvalidToken
from sqlalchemy import select

from app.core.security import _fernet
from app.database import AsyncSessionLocal
from app.models.integration import Integration, WalletAddress
from app.models.user import User

logger = logging.getLogger("rotate_fernet")


def _rotate_token(token: str | None) -> tuple[str | None, bool]:
    """Tek bir token'ı rotate eder. (yeni_token, basari) döner.
    None geçilirse no-op (None, True) döner — opsiyonel alanlar için."""
    if token is None:
        return None, True
    try:
        new_bytes = _fernet.rotate(token.encode())
        return new_bytes.decode(), True
    except InvalidToken:
        return None, False


async def rotate_all(dry_run: bool, batch_size: int) -> int:
    """3 tabloyu rotate eder. Hata sayısı döner (0 = tam başarı)."""
    errors = 0
    successes = 0

    async with AsyncSessionLocal() as db:
        # 1. wallet_addresses.address_encrypted
        logger.info("[1/3] wallet_addresses taranıyor...")
        result = await db.execute(select(WalletAddress))
        wallets = list(result.scalars().all())
        for batch_start in range(0, len(wallets), batch_size):
            batch = wallets[batch_start : batch_start + batch_size]
            for w in batch:
                new_ct, ok = _rotate_token(w.address_encrypted)
                if ok and new_ct is not None:
                    if not dry_run:
                        w.address_encrypted = new_ct
                    successes += 1
                else:
                    errors += 1
                    logger.warning("wallet_addresses.id=%s decrypt başarısız (eski key eksik?)", w.id)
            if not dry_run:
                await db.commit()
            logger.info("  wallet_addresses: %d/%d", min(batch_start + batch_size, len(wallets)), len(wallets))

        # 2. integrations.encrypted_key + encrypted_secret
        logger.info("[2/3] integrations taranıyor...")
        result = await db.execute(select(Integration))
        ints = list(result.scalars().all())
        for batch_start in range(0, len(ints), batch_size):
            batch = ints[batch_start : batch_start + batch_size]
            for i in batch:
                for col in ("encrypted_key", "encrypted_secret"):
                    val = getattr(i, col, None)
                    if val is None:
                        continue
                    new_ct, ok = _rotate_token(val)
                    if ok and new_ct is not None:
                        if not dry_run:
                            setattr(i, col, new_ct)
                        successes += 1
                    else:
                        errors += 1
                        logger.warning("integrations.id=%s %s decrypt başarısız", i.id, col)
            if not dry_run:
                await db.commit()
            logger.info("  integrations: %d/%d", min(batch_start + batch_size, len(ints)), len(ints))

        # 3. users.totp_secret (NULL olabilir, sadece MFA enabled kullanıcılar)
        logger.info("[3/3] users.totp_secret taranıyor (MFA aktif olanlar)...")
        result = await db.execute(select(User).where(User.totp_secret.isnot(None)))
        users = list(result.scalars().all())
        for batch_start in range(0, len(users), batch_size):
            batch = users[batch_start : batch_start + batch_size]
            for u in batch:
                new_ct, ok = _rotate_token(u.totp_secret)
                if ok and new_ct is not None:
                    if not dry_run:
                        u.totp_secret = new_ct
                    successes += 1
                else:
                    errors += 1
                    logger.warning("users.id=%s totp_secret decrypt başarısız", u.id)
            if not dry_run:
                await db.commit()
            logger.info("  users.totp_secret: %d/%d", min(batch_start + batch_size, len(users)), len(users))

    logger.info("=" * 60)
    logger.info("ROTATE TAMAMLANDI — başarı: %d, hata: %d (dry_run=%s)", successes, errors, dry_run)
    if errors == 0 and not dry_run:
        logger.info("Güvenli: FERNET_KEYS_SECONDARY env'i artık boşaltılabilir.")
    elif errors > 0:
        logger.warning("HATA(LAR) var — eski key eksik olabilir; rotate öncesi inceleyin.")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="DB'ye yazma; sadece decrypt başarısını kontrol et")
    parser.add_argument("--batch-size", type=int, default=100, help="Tek commit'te işlenecek satır sayısı (default 100)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    errors = asyncio.run(rotate_all(dry_run=args.dry_run, batch_size=args.batch_size))
    return 1 if errors > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
