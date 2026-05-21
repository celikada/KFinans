"""
Security primitives — JWT, bcrypt, Fernet (+ MultiFernet rotation).
DB veya HTTP gerekmez; saf birim testler.
"""

import time
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.fernet import Fernet
from jose import jwt as jose_jwt
from jose.exceptions import ExpiredSignatureError, JWTError

from app.config import settings
from app.core.security import (
    _build_fernet,
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


# ─── MultiFernet — Key Rotation (SEC-012) ────────────────────────────────────


class TestMultiFernetKeyRotation:
    """SEC-012: MultiFernet primary+secondary key rotation pattern.

    `_build_fernet()` settings okur. Test'lerde monkeypatch ile secondary
    listesini override edip in-process davranisi dogrularis.
    """

    def test_empty_secondaries_equivalent_to_single_key(self):
        """Default (bos liste) durumda tek-key Fernet ile ayni davranis."""
        f = _build_fernet()
        plain = "test-payload-default"
        ct = f.encrypt(plain.encode())
        assert f.decrypt(ct).decode() == plain

    def test_rotation_old_ciphertext_still_decrypts(self, monkeypatch):
        """Senaryoda: Eski primary ile encrypt edilen veri, rotation sonrasi
        yeni primary altinda secondary olarak listelenince hala decrypt olur."""
        old_key = Fernet.generate_key().decode()
        new_key = Fernet.generate_key().decode()

        # 1) ESKI primary ile cipher uret (sadece bu test icin direkt)
        old_fernet = Fernet(old_key.encode())
        ciphertext = old_fernet.encrypt(b"eski-aktif-veri")

        # 2) Rotation: primary=new, secondary=[old]
        monkeypatch.setattr(settings, "fernet_key", new_key)
        monkeypatch.setattr(settings, "fernet_keys_secondary", [old_key])
        rotated = _build_fernet()

        # 3) Eski cipher hala okunabilir (secondary sayesinde)
        assert rotated.decrypt(ciphertext).decode() == "eski-aktif-veri"

    def test_rotation_new_encryption_uses_primary(self, monkeypatch):
        """Encrypt SADECE primary ile yapilir — secondary plaintext'i kabul etmez."""
        old_key = Fernet.generate_key().decode()
        new_key = Fernet.generate_key().decode()

        monkeypatch.setattr(settings, "fernet_key", new_key)
        monkeypatch.setattr(settings, "fernet_keys_secondary", [old_key])
        rotated = _build_fernet()

        ct = rotated.encrypt(b"yeni-veri")

        # Yeni primary ile direkt decrypt olmali
        new_fernet_only = Fernet(new_key.encode())
        assert new_fernet_only.decrypt(ct) == b"yeni-veri"

        # Eski key tek basina yeni cipher'i ACAMAZ
        old_fernet_only = Fernet(old_key.encode())
        with pytest.raises(Exception):  # InvalidToken
            old_fernet_only.decrypt(ct)

    def test_multiple_secondaries_all_accepted(self, monkeypatch):
        """3 eski + 1 yeni primary — her birinden uretilen cipher decrypt olmali."""
        keys = [Fernet.generate_key().decode() for _ in range(4)]
        primary, secondaries = keys[0], keys[1:]

        # Her secondary key ile bir cipher uret
        ciphers = [
            Fernet(k.encode()).encrypt(f"data-from-key-{i}".encode())
            for i, k in enumerate(secondaries)
        ]

        monkeypatch.setattr(settings, "fernet_key", primary)
        monkeypatch.setattr(settings, "fernet_keys_secondary", secondaries)
        multi = _build_fernet()

        for i, ct in enumerate(ciphers):
            assert multi.decrypt(ct).decode() == f"data-from-key-{i}"

    def test_unknown_key_ciphertext_rejected(self, monkeypatch):
        """Ne primary ne secondary listesinde olan key ile uretilen cipher
        InvalidToken raise eder — saldirgan rastgele Fernet token uydurursa fail."""
        from cryptography.fernet import InvalidToken

        primary = Fernet.generate_key().decode()
        secondary = Fernet.generate_key().decode()
        rogue_key = Fernet.generate_key().decode()

        monkeypatch.setattr(settings, "fernet_key", primary)
        monkeypatch.setattr(settings, "fernet_keys_secondary", [secondary])
        multi = _build_fernet()

        rogue_ct = Fernet(rogue_key.encode()).encrypt(b"saldirgan-cipher")
        with pytest.raises(InvalidToken):
            multi.decrypt(rogue_ct)

    def test_empty_string_entries_in_secondary_skipped(self, monkeypatch):
        """Env'den gelen liste bos string'ler icerebilir (FERNET_KEYS_SECONDARY=
        '["", "real-key"]'); bunlar atlanmalI — `Fernet('')` patlamamali."""
        primary = Fernet.generate_key().decode()
        real_secondary = Fernet.generate_key().decode()

        monkeypatch.setattr(settings, "fernet_key", primary)
        # Bos string + gercek key karisik
        monkeypatch.setattr(settings, "fernet_keys_secondary", ["", real_secondary, ""])
        multi = _build_fernet()  # patlamamali

        ct = Fernet(real_secondary.encode()).encrypt(b"hayatta-kalan-veri")
        assert multi.decrypt(ct) == b"hayatta-kalan-veri"
