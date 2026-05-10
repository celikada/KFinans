"""SEC-003 (FAZ H): Multi-replica rate limit baypasi.

slowapi default MemoryStorage her pod'da ayri sayar -> N replica = N x kota.
settings.redis_url set ise Redis backend kullanilir; tum replica'lar ayni
key uzerinde sayim yapar. Production multi-replica zorunlu — yoksa K8s
replicas=1 sinirli olarak guvenli.
"""
import logging
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings

logger = logging.getLogger(__name__)


def _build_limiter() -> Limiter:
    if settings.redis_url:
        logger.info("Rate limiter Redis backend ile baslatildi: %s", _safe_url(settings.redis_url))
        return Limiter(key_func=get_remote_address, storage_uri=settings.redis_url)
    logger.info("Rate limiter MemoryStorage ile baslatildi (multi-replica icin Redis gerek)")
    return Limiter(key_func=get_remote_address)


def _safe_url(url: str) -> str:
    """Sifre alanlarini gizle: redis://user:pass@host -> redis://user:***@host"""
    if "@" not in url:
        return url
    proto, rest = url.split("://", 1) if "://" in url else ("", url)
    creds, host = rest.split("@", 1)
    if ":" in creds:
        user, _ = creds.split(":", 1)
        creds = f"{user}:***"
    return f"{proto}://{creds}@{host}" if proto else f"{creds}@{host}"


limiter = _build_limiter()
