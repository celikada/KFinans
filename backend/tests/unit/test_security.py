"""
Security primitives — JWT, bcrypt, Fernet.
DB veya HTTP gerekmez; saf birim testler.
"""
import time
from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt as jose_jwt
from jose.exceptions import ExpiredSignatureError, JWTError

from app.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    decrypt_secret,
    encrypt_secret,
    hash_password,
    verify_password,
)


# ─── Password Hashing ─────────────────────────────────────────────────────────

class TestPasswordHashing:
    def test_hash_is_different_from_plaintext(self):
        plain = "guclu-sifre-123"
        hashed = hash_password(plain)
        assert hashed != plain
        assert hashed.startswith("$2b$")  # bcrypt prefix

    def test_same_password_produces_different_hashes(self):
        plain = "ayni-sifre"
        h1 = hash_password(plain)
        h2 = hash_password(plain)
        assert h1 != h2  # salt randomness

    def test_verify_accepts_correct_password(self):
        hashed = hash_password("dogru-sifre")
        assert verify_password("dogru-sifre", hashed) is True

    def test_verify_rejects_wrong_password(self):
        hashed = hash_password("dogru-sifre")
        assert verify_password("yanlis-sifre", hashed) is False

    def test_verify_rejects_empty_password(self):
        hashed = hash_password("dogru-sifre")
        assert verify_password("", hashed) is False

    def test_unicode_password_works(self):
        plain = "şifrem-İçinde-türkçe-karakter-ñ"
        hashed = hash_password(plain)
        assert verify_password(plain, hashed) is True


# ─── JWT Tokens ───────────────────────────────────────────────────────────────

class TestJwtTokens:
    USER_ID = "11111111-2222-3333-4444-555555555555"

    def test_access_token_decodes_with_correct_subject(self):
        token = create_access_token(self.USER_ID)
        payload = decode_token(token)
        assert payload["sub"] == self.USER_ID

    def test_refresh_token_has_type_claim(self):
        token = create_refresh_token(self.USER_ID)
        payload = decode_token(token)
        assert payload["type"] == "refresh"
        assert payload["sub"] == self.USER_ID

    def test_access_token_does_not_have_refresh_type(self):
        token = create_access_token(self.USER_ID)
        payload = decode_token(token)
        assert payload.get("type") != "refresh"

    def test_token_has_expiration(self):
        token = create_access_token(self.USER_ID)
        payload = decode_token(token)
        assert "exp" in payload
        # exp should be in the future
        assert payload["exp"] > time.time()

    def test_refresh_token_lasts_longer_than_access(self):
        access = decode_token(create_access_token(self.USER_ID))
        refresh = decode_token(create_refresh_token(self.USER_ID))
        assert refresh["exp"] > access["exp"]

    def test_invalid_token_raises_jwt_error(self):
        with pytest.raises(JWTError):
            decode_token("not.a.valid.jwt")

    def test_token_signed_with_wrong_secret_fails(self):
        wrong_token = jose_jwt.encode(
            {"sub": self.USER_ID, "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
            "yanlis-secret",
            algorithm=settings.algorithm,
        )
        with pytest.raises(JWTError):
            decode_token(wrong_token)

    def test_expired_token_raises(self):
        expired = jose_jwt.encode(
            {"sub": self.USER_ID, "exp": datetime.now(timezone.utc) - timedelta(seconds=1)},
            settings.secret_key,
            algorithm=settings.algorithm,
        )
        with pytest.raises(ExpiredSignatureError):
            decode_token(expired)

    def test_tampered_token_fails(self):
        token = create_access_token(self.USER_ID)
        # Son karakteri değiştir → imza bozulur
        tampered = token[:-2] + ("AB" if token[-2:] != "AB" else "CD")
        with pytest.raises(JWTError):
            decode_token(tampered)


# ─── Fernet Encryption (Exchange API Keys) ────────────────────────────────────

class TestFernetEncryption:
    def test_encrypt_produces_different_output_than_plaintext(self):
        plain = "binance-api-key-12345"
        encrypted = encrypt_secret(plain)
        assert encrypted != plain
        assert len(encrypted) > len(plain)  # Fernet adds metadata

    def test_decrypt_restores_plaintext(self):
        plain = "secret-api-key"
        encrypted = encrypt_secret(plain)
        assert decrypt_secret(encrypted) == plain

    def test_encrypt_is_non_deterministic(self):
        """Fernet IV'si rasgele — aynı plaintext farklı ciphertext üretmeli."""
        plain = "ayni-secret"
        e1 = encrypt_secret(plain)
        e2 = encrypt_secret(plain)
        assert e1 != e2
        assert decrypt_secret(e1) == decrypt_secret(e2) == plain

    def test_decrypt_invalid_token_raises(self):
        with pytest.raises(Exception):  # InvalidToken
            decrypt_secret("bozuk-fernet-token")

    def test_decrypt_with_modified_ciphertext_raises(self):
        plain = "secret-data"
        encrypted = encrypt_secret(plain)
        modified = encrypted[:-4] + "XXXX"  # son 4 karakteri değiştir
        with pytest.raises(Exception):
            decrypt_secret(modified)

    def test_unicode_secret_works(self):
        plain = "şifre-içinde-türkçe-€-ñ"
        encrypted = encrypt_secret(plain)
        assert decrypt_secret(encrypted) == plain

    def test_long_secret_works(self):
        plain = "a" * 10_000
        encrypted = encrypt_secret(plain)
        assert decrypt_secret(encrypted) == plain
