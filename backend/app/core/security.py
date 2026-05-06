import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from jose import jwt
import bcrypt
from cryptography.fernet import Fernet
from app.config import settings

_fernet = Fernet(settings.fernet_key.encode())


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
