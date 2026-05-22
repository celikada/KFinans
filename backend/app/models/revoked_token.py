import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RevokedToken(Base):
    """Logout sonrasi blacklist'e alinan JWT'lerin jti'leri.

    JWT 'jti' (JWT ID) claim'i her token'da unique uuid4.hex; logout endpoint'i
    o jti'yi bu tabloya yazar. get_current_user ve refresh endpoint'i her
    istekte jti'nin burada olup olmadigini kontrol eder.

    expires_at periyodik temizlik icin tutulur (suresi dolmus tokenlar zaten
    JWT decode'da reddedilir, blacklist'te kalmasina gerek yok).
    """

    __tablename__ = "revoked_tokens"

    jti: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    # access | refresh
    token_type: Mapped[str] = mapped_column(String(10), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
