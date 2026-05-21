"""SEC (audit #5): Password policy unit testleri.

`check_password_strength` (zxcvbn) ve `check_hibp_pwned` (HIBP k-anonymity)
fonksiyonlarini izole olarak test eder. HIBP icin respx ile API mock'lanir;
gercek aga gidilmez.

Test edilen invariant'lar:
  - Zayif sifreler reddedilir (123456, password, qwerty)
  - Email/isim iceren sifreler reddedilir (zxcvbn user_inputs)
  - Guclu rastgele sifreler kabul edilir (skor >= 3)
  - HIBP bilinen sizmis hash'lere yanit doner -> leaked_count >= 1
  - HIBP bilinmeyen hash -> 0
  - HIBP timeout/network error -> fail-open (0)
  - HIBP non-200 response -> fail-open (0)
  - settings.hibp_check_enabled=False -> network cagrisi yok, 0 doner
"""
import hashlib

import httpx
import pytest
import respx

from app.config import settings
from app.core.password_policy import (
    _HIBP_RANGE_URL,
    check_hibp_pwned,
    check_password_strength,
)


# ─── check_password_strength ────────────────────────────────────────────────


class TestPasswordStrength:
    def test_very_common_password_rejected(self):
        """123456 zxcvbn'in 1. siradaki guess'i — score 0."""
        is_valid, msg = check_password_strength("123456")
        assert is_valid is False
        assert "zayif" in msg.lower() or "skor" in msg.lower()

    def test_password_word_rejected(self):
        """`password` kelimesi top-10 ortak sifre listesinde."""
        is_valid, _ = check_password_strength("password")
        assert is_valid is False

    def test_password_123_pattern_rejected(self):
        """password123 — base word + trailing digit pattern."""
        is_valid, _ = check_password_strength("password123")
        assert is_valid is False

    def test_qwerty_keyboard_pattern_rejected(self):
        is_valid, _ = check_password_strength("qwerty123")
        assert is_valid is False

    def test_password_containing_email_rejected(self):
        """Kullanici email'i + suffix -> zxcvbn user_inputs ile yakalanir."""
        is_valid, _ = check_password_strength(
            "AdaCelik2026!",
            user_inputs=["ada.celik@example.com", "ada.celik"],
        )
        assert is_valid is False

    def test_password_containing_local_part_rejected(self):
        """Local-part eslemesi de yakalanir."""
        is_valid, _ = check_password_strength(
            "celikada123!",
            user_inputs=["celikada@gmail.com", "celikada"],
        )
        assert is_valid is False

    def test_strong_random_password_accepted(self):
        """Yuksek entropy'li random string — score 4."""
        is_valid, msg = check_password_strength(
            "Tr0ub4dor&3-correct-horse-battery-staple",
        )
        assert is_valid is True
        assert msg == ""

    def test_diceware_phrase_accepted(self):
        """4-kelime diceware passphrase — score >= 3."""
        is_valid, _ = check_password_strength("kahve-bulut-meridyen-sokak-9421")
        assert is_valid is True

    def test_error_message_is_turkish_and_pii_safe(self):
        """Reddedilen sifre mesaji TR ve sifrenin kendisini icermez."""
        password = "MyP@ss123"
        is_valid, msg = check_password_strength(password)
        # Bu sifre score 2 civari — kabul edilmemeli
        if not is_valid:
            assert password not in msg
            assert "Sifre" in msg or "sifre" in msg.lower()

    def test_user_inputs_none_does_not_crash(self):
        """user_inputs=None default — zxcvbn'e bos liste verilir."""
        is_valid, _ = check_password_strength("verystrongpassword-9z!Q-meridyen")
        # Bu sifre score >= 3 olmali
        assert is_valid is True

    def test_user_inputs_with_none_elements_filtered(self):
        """full_name None olabilir — None elemanlar atlanir."""
        is_valid, _ = check_password_strength(
            "weakpw",
            user_inputs=["user@example.com", None],  # type: ignore[list-item]
        )
        # Hala zayif (ama crash etmemeli)
        assert is_valid is False


# ─── check_hibp_pwned ───────────────────────────────────────────────────────


def _hibp_response_with_password(password: str, count: int) -> str:
    """Verilen sifrenin SHA-1 hash'inin suffix'ini iceren HIBP response uret.

    HIBP response format: HASH_SUFFIX:COUNT (her satir bir hash).
    """
    sha1_hex = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()
    suffix = sha1_hex[5:]
    # Bir kac rastgele hash + bizim aradigimiz suffix
    return (
        "0018A45C4D1DEF81644B54AB7F969B88D65:5\r\n"
        "00D4F6E8FA6EECAD2A3AA415EEC418D38EC:2\r\n"
        f"{suffix}:{count}\r\n"
        "1E2DB1E66B348A1B9F77F1A6C6E1F86D7CB:1\r\n"
    )


class TestHibpPwned:
    PWNED_PASSWORD = "password123"  # Bilinen sizmis sifre (HIBP'de milyonlarca kez)

    @pytest.mark.asyncio
    async def test_known_pwned_password_returns_leak_count(self):
        """Mock'lanan HIBP response 12345 leak gosterirse leaked_count=12345."""
        body = _hibp_response_with_password(self.PWNED_PASSWORD, 12345)
        prefix = hashlib.sha1(self.PWNED_PASSWORD.encode()).hexdigest().upper()[:5]

        with respx.mock:
            respx.get(_HIBP_RANGE_URL.format(prefix=prefix)).mock(
                return_value=httpx.Response(200, text=body),
            )
            count = await check_hibp_pwned(self.PWNED_PASSWORD)
        assert count == 12345

    @pytest.mark.asyncio
    async def test_unknown_password_returns_zero(self):
        """Suffix response'da yoksa leaked_count=0."""
        prefix = hashlib.sha1(b"unique-random-password-987654").hexdigest().upper()[:5]
        # Response'da hicbir suffix bizim sifremize uymuyor
        body = (
            "0018A45C4D1DEF81644B54AB7F969B88D65:5\r\n"
            "00D4F6E8FA6EECAD2A3AA415EEC418D38EC:2\r\n"
        )
        with respx.mock:
            respx.get(_HIBP_RANGE_URL.format(prefix=prefix)).mock(
                return_value=httpx.Response(200, text=body),
            )
            count = await check_hibp_pwned("unique-random-password-987654")
        assert count == 0

    @pytest.mark.asyncio
    async def test_timeout_returns_zero_fail_open(self):
        """Network timeout -> fail-open (0). Kullanici bloklanmaz."""
        with respx.mock:
            respx.get(url__regex=r"https://api\.pwnedpasswords\.com/range/.*").mock(
                side_effect=httpx.TimeoutException("timeout"),
            )
            count = await check_hibp_pwned("any-password", timeout=0.5)
        assert count == 0

    @pytest.mark.asyncio
    async def test_network_error_returns_zero_fail_open(self):
        """ConnectError gibi network hatasi -> fail-open."""
        with respx.mock:
            respx.get(url__regex=r"https://api\.pwnedpasswords\.com/range/.*").mock(
                side_effect=httpx.ConnectError("connection refused"),
            )
            count = await check_hibp_pwned("any-password")
        assert count == 0

    @pytest.mark.asyncio
    async def test_non_200_response_returns_zero_fail_open(self):
        """HIBP 503 / 429 -> fail-open."""
        prefix = hashlib.sha1(b"some-pw").hexdigest().upper()[:5]
        with respx.mock:
            respx.get(_HIBP_RANGE_URL.format(prefix=prefix)).mock(
                return_value=httpx.Response(503, text="service unavailable"),
            )
            count = await check_hibp_pwned("some-pw")
        assert count == 0

    @pytest.mark.asyncio
    async def test_disabled_setting_skips_network_call(self, monkeypatch):
        """settings.hibp_check_enabled=False -> hic API cagirilmaz, 0 doner."""
        monkeypatch.setattr(settings, "hibp_check_enabled", False)
        with respx.mock:
            # Hicbir mock route tanimlamadik — gercek call patlardi.
            count = await check_hibp_pwned("password123")
        assert count == 0

    @pytest.mark.asyncio
    async def test_malformed_response_line_ignored(self):
        """Bozuk satirlar (": yok, count non-int) sessizce atlanir."""
        prefix = hashlib.sha1(b"any").hexdigest().upper()[:5]
        body = (
            "INVALID_LINE_NO_COLON\r\n"
            "ABCDE:not_a_number\r\n"
            "0018A45C4D1DEF81644B54AB7F969B88D65:5\r\n"
        )
        with respx.mock:
            respx.get(_HIBP_RANGE_URL.format(prefix=prefix)).mock(
                return_value=httpx.Response(200, text=body),
            )
            count = await check_hibp_pwned("any")
        assert count == 0

    @pytest.mark.asyncio
    async def test_only_prefix_sent_not_full_hash(self):
        """K-anonymity invariant: API'ye sadece ilk 5 char gider, tam hash YOK."""
        password = "test-anonymity-property"
        sha1_full = hashlib.sha1(password.encode()).hexdigest().upper()
        prefix = sha1_full[:5]

        captured_url: dict[str, str] = {}

        def _capture(request):
            captured_url["url"] = str(request.url)
            return httpx.Response(200, text="")

        with respx.mock:
            respx.get(_HIBP_RANGE_URL.format(prefix=prefix)).mock(side_effect=_capture)
            await check_hibp_pwned(password)

        assert prefix in captured_url["url"]
        # Tam hash kesinlikle URL'de olmamali
        assert sha1_full not in captured_url["url"]
        # Sifre kendisi de URL'de olmamali
        assert password not in captured_url["url"]
