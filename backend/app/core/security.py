import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from jose import jwt
import bcrypt
from cryptography.fernet import Fernet, MultiFernet
from app.config import settings


def _build_fernet() -> MultiFernet:
    """SEC-012 (FAZ H): MultiFernet with primary + optional secondaries.

    Encrypt uses ONLY the primary (first) key; decrypt walks the list and
    accepts ciphertext encrypted with ANY key. This enables zero-downtime key
    rotation:

      Primary (settings.fernet_key) -> encrypt + decrypt
      Secondaries (settings.fernet_keys_secondary) -> decrypt only

    When `fernet_keys_secondary` is empty (default), behavior is identical to
    a single-key Fernet (backward compatible).

    Invalid base64 in any key raises at import time — fail-fast.
    """
    primary = Fernet(settings.fernet_key.encode())
    secondaries = [Fernet(k.encode()) for k in settings.fernet_keys_secondary if k]
    return MultiFernet([primary, *secondaries])


_fernet = _build_fernet()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode(
        {"sub": subject, "exp": expire, "jti": uuid.uuid4().hex},
        settings.secret_key,
        algorithm=settings.algorithm,
    )


def create_refresh_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    return jwt.encode(
        {"sub": subject, "exp": expire, "type": "refresh", "jti": uuid.uuid4().hex},
        settings.secret_key,
        algorithm=settings.algorithm,
    )


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])


# MFA — TOTP (audit #5 MFA).
# pre_mfa_token: login basarili (email+password) ama TOTP henuz dogrulanmadi.
# `type=pre_mfa` scope sadece /mfa/verify endpoint'inde gecerli; access token
# olarak kullanilamaz (get_current_user `type` kontrol etmiyor ama mfa.verify
# explicit dogrular). 15 dk TTL — kullanici kod girip submit'lemek icin yeterli.
PRE_MFA_TOKEN_TTL_SECONDS = 15 * 60


def create_pre_mfa_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(seconds=PRE_MFA_TOKEN_TTL_SECONDS)
    return jwt.encode(
        {"sub": subject, "exp": expire, "type": "pre_mfa", "jti": uuid.uuid4().hex},
        settings.secret_key,
        algorithm=settings.algorithm,
    )


def encrypt_secret(value: str) -> str:
    return _fernet.encrypt(value.encode()).decode()


def decrypt_secret(value: str) -> str:
    return _fernet.decrypt(value.encode()).decode()


def address_fingerprint(address: str) -> str:
    """SHA-256 hex digest of lowercase address.

    Used for unique-constraint lookups on encrypted wallet addresses where
    plaintext WHERE filtering is not possible. Lowercase normalization makes
    EVM checksum variants collide (intended) and is no-op for Bech32/base58/
    xpub formats which are conventionally lowercase.
    """
    return hashlib.sha256(address.lower().encode("utf-8")).hexdigest()
