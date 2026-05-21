"""Wallet address Fernet sifreleme + SHA-256 fingerprint

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-05-06 21:00:00.000000

Bitcoin xpub ve diger blockchain cuzdan adresleri DB sizintisinda saldirgana
kullanicinin bakiye gecmisini gorme imkani veriyordu (xpub'tan tum child
public key'ler turetilebilir). Bu migration:

  1. address_encrypted (Fernet ciphertext) ve address_fingerprint (SHA-256
     hex of lowercase address) kolonlarini ekler.
  2. Mevcut plaintext address kayitlarini sifreler ve fingerprint hesaplar.
  3. Eski 'address' kolonunu ve uniqueness constraint'ini siler.
  4. Fingerprint bazli yeni unique constraint ekler.

KRITIK: Bu migration FERNET_KEY'in mevcut env'den okunabildigi varsayar.
Production'da deploy oncesi key'in dogru ayarlandigindan emin olun. Key
yanlissa upgrade fail eder; downgrade ile geri donulebilir (sifreleme
oncesi state).
"""

import sqlalchemy as sa

from alembic import op

revision = "b3c4d5e6f7a8"
down_revision = "a2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Yeni kolonlari ekle (gecici nullable, data migration sonrasi NOT NULL)
    op.add_column(
        "wallet_addresses",
        sa.Column("address_encrypted", sa.Text(), nullable=True),
    )
    op.add_column(
        "wallet_addresses",
        sa.Column("address_fingerprint", sa.String(64), nullable=True),
    )

    # 2. Mevcut plaintext address'leri sifrele + fingerprint hesapla
    # Inline icinde encrypt_secret + address_fingerprint cagirmak icin
    # uygulamanin Fernet helper'larini import ediyoruz.
    from app.core.security import address_fingerprint, encrypt_secret

    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, address FROM wallet_addresses")).fetchall()

    for row in rows:
        wallet_id = row[0]
        plaintext = row[1]
        if plaintext is None:
            continue
        ciphertext = encrypt_secret(plaintext)
        fp = address_fingerprint(plaintext)
        bind.execute(
            sa.text(
                "UPDATE wallet_addresses "
                "SET address_encrypted = :enc, address_fingerprint = :fp "
                "WHERE id = :id"
            ),
            {"enc": ciphertext, "fp": fp, "id": wallet_id},
        )

    # 3. Eski unique constraint'i ve plaintext kolonu sil
    op.drop_constraint("uq_wallet_user_chain_address", "wallet_addresses", type_="unique")
    op.drop_column("wallet_addresses", "address")

    # 4. Yeni kolonlari NOT NULL'a cevir + index + unique constraint
    op.alter_column("wallet_addresses", "address_encrypted", nullable=False)
    op.alter_column("wallet_addresses", "address_fingerprint", nullable=False)
    op.create_index(
        "ix_wallet_addresses_fingerprint",
        "wallet_addresses",
        ["address_fingerprint"],
    )
    op.create_unique_constraint(
        "uq_wallet_user_chain_fp",
        "wallet_addresses",
        ["user_id", "chain", "address_fingerprint"],
    )


def downgrade() -> None:
    # Sifrelemeyi geri al: address_encrypted -> address (plaintext)
    op.add_column(
        "wallet_addresses",
        sa.Column("address", sa.Text(), nullable=True),
    )

    from app.core.security import decrypt_secret

    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, address_encrypted FROM wallet_addresses")).fetchall()

    for row in rows:
        wallet_id = row[0]
        ciphertext = row[1]
        if ciphertext is None:
            continue
        plaintext = decrypt_secret(ciphertext)
        bind.execute(
            sa.text("UPDATE wallet_addresses SET address = :addr WHERE id = :id"),
            {"addr": plaintext, "id": wallet_id},
        )

    # Yeni constraint + index'i temizle
    op.drop_constraint("uq_wallet_user_chain_fp", "wallet_addresses", type_="unique")
    op.drop_index("ix_wallet_addresses_fingerprint", "wallet_addresses")
    op.drop_column("wallet_addresses", "address_encrypted")
    op.drop_column("wallet_addresses", "address_fingerprint")

    # Eski state'i restore et
    op.alter_column("wallet_addresses", "address", nullable=False)
    op.create_unique_constraint(
        "uq_wallet_user_chain_address",
        "wallet_addresses",
        ["user_id", "chain", "address"],
    )
