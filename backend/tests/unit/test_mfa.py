"""MFA TOTP saf birim testler — pyotp + bcrypt + helper logic.

DB / HTTP yok. Endpoint testleri tests/integration/test_mfa.py'da.
"""

import json

import bcrypt
import pyotp

from app.api.v1.mfa import (
    _build_qr_png_base64,
    _generate_recovery_codes,
    _hash_recovery_code,
    _verify_recovery_code,
)
from app.core.security import (
    PRE_MFA_TOKEN_TTL_SECONDS,
    create_pre_mfa_token,
    decode_token,
)


class TestTotpEncodeDecode:
    def test_random_base32_secret_uretir(self):
        secret = pyotp.random_base32()
        # base32 alfabesi A-Z 2-7
        assert len(secret) == 32
        assert all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567" for c in secret)

    def test_totp_verify_dogru_kod_kabul_eder(self):
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        current_code = totp.now()
        assert totp.verify(current_code, valid_window=1) is True

    def test_totp_verify_yanlis_kod_reddeder(self):
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        # 000000 cok yuksek olasilikla yanlis (1/10^6 false positive ihtimali)
        assert totp.verify("000000", valid_window=1) is False

    def test_provisioning_uri_otpauth_formatinda(self):
        secret = pyotp.random_base32()
        uri = pyotp.TOTP(secret).provisioning_uri(
            name="user@example.com",
            issuer_name="KFinans",
        )
        assert uri.startswith("otpauth://totp/KFinans:user@example.com")
        assert f"secret={secret}" in uri
        assert "issuer=KFinans" in uri


class TestRecoveryCodes:
    def test_generate_returns_10_unique_hex_codes(self):
        codes = _generate_recovery_codes(10)
        assert len(codes) == 10
        assert len(set(codes)) == 10  # tum kodlar farkli
        for c in codes:
            assert len(c) == 12  # token_hex(6) = 12 hex chars
            int(c, 16)  # gecerli hex parse edilir

    def test_hash_recovery_code_bcrypt_format(self):
        code = "abcdef123456"
        hashed = _hash_recovery_code(code)
        # bcrypt $2a$ veya $2b$ prefix
        assert hashed.startswith("$2")
        assert hashed != code

    def test_verify_recovery_code_match(self):
        code = "abcdef123456"
        hashed = _hash_recovery_code(code)
        assert _verify_recovery_code(code, hashed) is True
        assert _verify_recovery_code("wrong_code", hashed) is False

    def test_verify_recovery_code_invalid_hash_safe(self):
        # Kotu formatli hash crash etmemeli; False donmeli.
        assert _verify_recovery_code("test", "not-a-bcrypt-hash") is False
        assert _verify_recovery_code("test", "") is False


class TestQrPngGeneration:
    def test_qr_png_base64_data_url_format(self):
        uri = "otpauth://totp/KFinans:test@example.com?secret=ABC&issuer=KFinans"
        data_url = _build_qr_png_base64(uri)
        assert data_url.startswith("data:image/png;base64,")
        # base64 kismi en az birkac yuz byte (QR PNG icin tipik)
        b64_part = data_url.split(",", 1)[1]
        assert len(b64_part) > 100


class TestPreMfaToken:
    def test_create_pre_mfa_token_decode_eder(self):
        token = create_pre_mfa_token("user-id-123")
        data = decode_token(token)
        assert data["sub"] == "user-id-123"
        assert data["type"] == "pre_mfa"
        assert "jti" in data
        assert "exp" in data

    def test_pre_mfa_token_15_dakika_ttl(self):
        assert PRE_MFA_TOKEN_TTL_SECONDS == 15 * 60


class TestRecoveryCodeJsonSerialization:
    def test_hashlist_json_roundtrip(self):
        """totp_recovery_codes Text alaninda JSON list[str] olarak yazilir."""
        codes = _generate_recovery_codes(10)
        hashed = [_hash_recovery_code(c) for c in codes]
        serialized = json.dumps(hashed)
        parsed = json.loads(serialized)
        assert parsed == hashed
        # Plaintext kodlardan en az biri kendi hash'iyle eslesir
        assert any(bcrypt.checkpw(codes[0].encode(), h.encode()) for h in parsed)


class TestSecretEncryptionRoundTrip:
    def test_totp_secret_fernet_roundtrip(self):
        """encrypt_secret/decrypt_secret base32 string'i bozmadan tasir."""
        from app.core.security import decrypt_secret, encrypt_secret

        secret = pyotp.random_base32()
        encrypted = encrypt_secret(secret)
        assert encrypted != secret
        decrypted = decrypt_secret(encrypted)
        assert decrypted == secret
        # Sifre cozuldukten sonra hala gecerli TOTP secret
        totp = pyotp.TOTP(decrypted)
        assert totp.verify(totp.now(), valid_window=1) is True
