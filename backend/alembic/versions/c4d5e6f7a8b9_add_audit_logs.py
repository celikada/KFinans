"""audit_logs tablosu ekle

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-05-06 22:30:00.000000

KVKK m.12 + Veri Ihlali Bildirim prosedurleri icin kritik kullanici
eylemlerinin denetim kaydi. Loglanan eylemler:
  - auth.login, auth.logout, auth.password_change, auth.login_failed
  - integration.add, integration.delete
  - wallet.add, wallet.delete
  - kvkk.data_export
  - snapshot.delete
  - account.soft_delete

Index'ler:
  - (user_id, created_at DESC) — user kendi log'larini hizli gorur
  - (action, created_at DESC) — admin/security tipe gore arama
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision = "c4d5e6f7a8b9"
down_revision = "b3c4d5e6f7a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("resource", sa.String(128), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column("extra", JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_audit_logs_user_created", "audit_logs", ["user_id", "created_at"])
    op.create_index("ix_audit_logs_action_created", "audit_logs", ["action", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_action_created", "audit_logs")
    op.drop_index("ix_audit_logs_user_created", "audit_logs")
    op.drop_table("audit_logs")
