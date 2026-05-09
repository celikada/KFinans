"""DBA-001 + SEC-002 (FAZ H): FK CASCADE + account lockout kolonlari.

DBA-001: 5 FK'da ondelete kuralsizdi -> NO ACTION (default). pg_dump restore
ya da dogrudan SQL DELETE'te FK violation. ORM cascade Python-only kalmasin
diye DB seviyesinde de CASCADE/SET NULL ekledik.

  integrations.user_id        -> CASCADE
  wallet_addresses.user_id    -> CASCADE
  portfolio_snapshots.user_id -> CASCADE
  asset_positions.snapshot_id -> CASCADE
  asset_positions.wallet_address_id -> SET NULL (history koru)
  investment_advice.user_id   -> CASCADE
  investment_advice.snapshot_id -> SET NULL

SEC-002: users.failed_login_count + users.locked_until kolonlari (account
lockout - OWASP ASVS V2.2.1).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f7a8b9c0d1e2"
down_revision = "e6f7a8b9c0d1"
branch_labels = None
depends_on = None


# (table, fk_column, referenced_table, on_delete) tuple'lari.
# PostgreSQL'de constraint adlari naming convention: {table}_{column}_fkey.
_CASCADE_FKS = [
    ("integrations", "user_id", "users", "CASCADE"),
    ("wallet_addresses", "user_id", "users", "CASCADE"),
    ("portfolio_snapshots", "user_id", "users", "CASCADE"),
    ("asset_positions", "snapshot_id", "portfolio_snapshots", "CASCADE"),
    ("asset_positions", "wallet_address_id", "wallet_addresses", "SET NULL"),
    ("investment_advice", "user_id", "users", "CASCADE"),
    ("investment_advice", "snapshot_id", "portfolio_snapshots", "SET NULL"),
]


def upgrade() -> None:
    # ─── DBA-001: FK ondelete -> CASCADE/SET NULL ────────────────────────
    for table, col, ref_table, on_delete in _CASCADE_FKS:
        constraint = f"{table}_{col}_fkey"
        op.drop_constraint(constraint, table, type_="foreignkey")
        op.create_foreign_key(
            constraint, table, ref_table,
            [col], ["id"],
            ondelete=on_delete,
        )

    # ─── SEC-002: account lockout kolonlari ──────────────────────────────
    op.add_column(
        "users",
        sa.Column(
            "failed_login_count", sa.Integer(),
            nullable=False, server_default="0",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "locked_until", sa.TIMESTAMP(timezone=True), nullable=True,
        ),
    )


def downgrade() -> None:
    # SEC-002 geri al
    op.drop_column("users", "locked_until")
    op.drop_column("users", "failed_login_count")

    # DBA-001 geri al — FK'lar default (NO ACTION) durumuna
    for table, col, ref_table, _ in _CASCADE_FKS:
        constraint = f"{table}_{col}_fkey"
        op.drop_constraint(constraint, table, type_="foreignkey")
        op.create_foreign_key(
            constraint, table, ref_table,
            [col], ["id"],
        )
