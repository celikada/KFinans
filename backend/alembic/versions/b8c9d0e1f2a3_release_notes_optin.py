"""Sürüm bildirimleri (release notes) opt-in alanları.

users tablosuna 3 kolon:
1. `is_admin` — release notes gönderme endpoint'i için yetki flag'i
   (sistemde rol yok; server default False).
2. `release_notes_opt_in` — KVKK açık rıza, kayıtta varsayılan KAPALI.
3. `unsubscribe_token` — kalıcı user-özel token (auth'suz mail içi unsubscribe
   linki için). Unique index.
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "b8c9d0e1f2a3"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_admin", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "users",
        sa.Column("release_notes_opt_in", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "users",
        sa.Column("unsubscribe_token", sa.Text(), nullable=True),
    )
    op.create_index(
        "uq_users_unsubscribe_token",
        "users",
        ["unsubscribe_token"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_users_unsubscribe_token", table_name="users")
    op.drop_column("users", "unsubscribe_token")
    op.drop_column("users", "release_notes_opt_in")
    op.drop_column("users", "is_admin")
