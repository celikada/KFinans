"""SEC-001 (FAZ H): users.reset_token + reset_token_expires_at.

OWASP Forgot Password Cheat Sheet — secrets.token_urlsafe(32) token, 1 saat TTL.
verify_token pattern'i kopyalanir (idempotent rotation, generic response).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a8b9c0d1e2f3"
down_revision = "f7a8b9c0d1e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("reset_token", sa.Text(), nullable=True))
    op.add_column(
        "users",
        sa.Column("reset_token_expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index("ix_users_reset_token", "users", ["reset_token"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_users_reset_token", table_name="users")
    op.drop_column("users", "reset_token_expires_at")
    op.drop_column("users", "reset_token")
