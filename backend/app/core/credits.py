"""Faz 3 kredi sistemi — bakiye dusum/yukleme helper'lari.

Tutarlilik invaryanti (mimar karari, doc 06 §8.3): HER bakiye degisimi tek
transaction'da hem `credit_transactions` insert hem `users.credit_balance`
update icerir. Bu helper'lar **commit ETMEZ** — yalnizca flush eder; commit
caller'a birakilir (advice.py'nin tek-transaction atomiklik garantisi icin
kritik; log_audit ile ayni felsefe). SELECT ... FOR UPDATE ile satir kilidi
yaris durumunu onler (cok-kullanicili satin alma akisi geldiginde de hazir).
"""

from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.credit_transaction import CreditTransaction
from app.models.user import User


async def deduct_credits(
    db: AsyncSession,
    *,
    user_id,
    amount: int,
    reason: str,
    reference_id: Optional[str] = None,
    extra: Optional[dict] = None,
) -> int:
    """Kullanicidan `amount` (pozitif) kredi dus + ledger'a negatif satir yaz.

    SELECT FOR UPDATE ile kullanici satirini kilitler; bakiye yetersizse 402
    firlatir (ledger'a satir yazilmaz). Yeni bakiyeyi dondurur. Commit ETMEZ.
    """
    if amount <= 0:
        raise ValueError("deduct_credits: amount pozitif olmali")

    user = (await db.execute(select(User).where(User.id == user_id).with_for_update())).scalar_one()

    if (user.credit_balance or 0) < amount:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Yetersiz kredi. Gerekli: {amount}, mevcut: {user.credit_balance or 0}.",
        )

    user.credit_balance = (user.credit_balance or 0) - amount
    db.add(
        CreditTransaction(
            user_id=user_id,
            amount=-amount,
            reason=reason,
            reference_id=reference_id,
            extra=extra,
        )
    )
    await db.flush()
    return user.credit_balance


async def add_credits(
    db: AsyncSession,
    *,
    user_id,
    amount: int,
    reason: str,
    reference_id: Optional[str] = None,
    idempotency_key: Optional[str] = None,
    extra: Optional[dict] = None,
) -> int:
    """Kullaniciya `amount` (pozitif) kredi ekle + ledger'a pozitif satir yaz.

    idempotency_key verildiyse: ayni key ile kayit varsa NO-OP (webhook
    cift-teslimat korumasi) — mevcut bakiyeyi dondurur. Commit ETMEZ.
    """
    if amount <= 0:
        raise ValueError("add_credits: amount pozitif olmali")

    if idempotency_key is not None:
        existing = (await db.execute(select(CreditTransaction.id).where(CreditTransaction.idempotency_key == idempotency_key))).first()
        if existing is not None:
            # Zaten islenmis — bakiyeyi degistirmeden dondur (idempotent).
            user = (await db.execute(select(User).where(User.id == user_id))).scalar_one()
            return user.credit_balance or 0

    user = (await db.execute(select(User).where(User.id == user_id).with_for_update())).scalar_one()

    user.credit_balance = (user.credit_balance or 0) + amount
    db.add(
        CreditTransaction(
            user_id=user_id,
            amount=amount,
            reason=reason,
            reference_id=reference_id,
            idempotency_key=idempotency_key,
            extra=extra,
        )
    )
    await db.flush()
    return user.credit_balance
