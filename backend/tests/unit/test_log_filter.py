"""PIIFilter unit tests (app/core/log_filter.py).

PII pattern'lerin doğru mask edildiğini ve normal log içeriğinin
bozulmadığını doğrular. install_pii_filter idempotent davranışı + handler
attachment davranışı test edilir.
"""

import logging

import pytest

from app.core.log_filter import PIIFilter, install_pii_filter


def _filter_message(msg: str, args: tuple = ()) -> str:
    """Bir log mesajını PIIFilter'dan geçirip dönen mesajı verir."""
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=args,
        exc_info=None,
    )
    PIIFilter().filter(record)
    return record.getMessage()


def test_email_masked():
    assert _filter_message("Kullanıcı ali@example.com giriş yaptı") == "Kullanıcı <email> giriş yaptı"


def test_email_with_plus_and_dot_masked():
    assert _filter_message("first.last+tag@sub.example.co") == "<email>"


def test_ipv4_masked():
    assert _filter_message("Request from 192.168.1.42") == "Request from <ip>"


def test_multiple_ips_masked():
    assert _filter_message("LB 10.0.0.1 → upstream 172.16.99.99") == "LB <ip> → upstream <ip>"


def test_jwt_masked():
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0In0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    assert _filter_message(f"Token: {jwt}") == "Token: <jwt>"


def test_bearer_opaque_token_masked():
    assert _filter_message("Authorization: Bearer abc123def456ghi789jkl012mno") == "Authorization: Bearer <token>"


def test_bearer_case_insensitive():
    assert _filter_message("authorization: bearer abc123def456ghi789jkl012mno") == "authorization: Bearer <token>"


def test_pan_with_spaces_masked():
    assert _filter_message("Kart no 4111 1111 1111 1111 onaylandı") == "Kart no <card> onaylandı"


def test_pan_with_dashes_masked():
    assert _filter_message("PAN: 4111-1111-1111-1111") == "PAN: <card>"


def test_pan_solid_masked():
    assert _filter_message("4111111111111111 reddedildi") == "<card> reddedildi"


def test_combined_pii_in_one_message():
    msg = "User ali@example.com from 192.168.1.1 used Bearer eyJhbGc.eyJzdWIi.signABC"
    masked = _filter_message(msg)
    assert "<email>" in masked
    assert "<ip>" in masked
    # JWT pattern Bearer'dan önce match etmeli
    assert "<jwt>" in masked
    assert "ali@" not in masked
    assert "192.168" not in masked


def test_no_pii_unchanged():
    msg = "Snapshot tamamlandı: 42 varlık, 1234.56 TL"
    assert _filter_message(msg) == msg


def test_args_substitution_applied_then_masked():
    """logger.info("user %s", email) → args substitusyonu PRE mask çalışır."""
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="user %s logged in",
        args=("ali@example.com",),
        exc_info=None,
    )
    PIIFilter().filter(record)
    assert record.getMessage() == "user <email> logged in"
    # args temizlendi — handler tekrar substitusyon yapmasın
    assert record.args == ()


def test_install_pii_filter_idempotent():
    """install_pii_filter aynı logger'a iki kez eklenmemeli."""
    test_logger = logging.getLogger("test_pii_idempotent")
    handler = logging.StreamHandler()
    test_logger.addHandler(handler)

    install_pii_filter(test_logger)
    install_pii_filter(test_logger)

    pii_filters = [f for f in handler.filters if isinstance(f, PIIFilter)]
    assert len(pii_filters) == 1


def test_install_pii_filter_adds_to_all_handlers():
    test_logger = logging.getLogger("test_pii_handlers")
    h1 = logging.StreamHandler()
    h2 = logging.StreamHandler()
    test_logger.addHandler(h1)
    test_logger.addHandler(h2)

    install_pii_filter(test_logger)

    assert any(isinstance(f, PIIFilter) for f in h1.filters)
    assert any(isinstance(f, PIIFilter) for f in h2.filters)


def test_invalid_args_does_not_crash():
    """msg formatlanamazsa filter kayıt geçer, mask yapmaz (safe failure)."""
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="user %s logged in from %s",
        args=("ali@example.com",),  # eksik arg
        exc_info=None,
    )
    # Crash etmemeli
    assert PIIFilter().filter(record) is True


def test_short_bearer_not_matched():
    """Çok kısa string Bearer pattern'i tetiklemez (false positive koruması)."""
    # 20 karakter altı opaque token Bearer pattern'i match etmez
    assert _filter_message("Bearer abc123") == "Bearer abc123"


def test_partial_jwt_not_matched():
    """JWT regex 3 segment ister; iki segment match etmez."""
    assert _filter_message("not a jwt: eyJhbGci.eyJzdWIi") == "not a jwt: eyJhbGci.eyJzdWIi"


def test_ipv4_invalid_oktet_count():
    """3 oktet IPv4 sayılmaz."""
    # NOTE: pattern \b(?:\d{1,3}\.){3}\d{1,3}\b ile "1.2.3" match etmez
    assert _filter_message("port 1.2.3 servisi") == "port 1.2.3 servisi"


@pytest.mark.parametrize(
    "value",
    [
        "simple@x.io",
        "long.name+tag@example.co.uk",
        "USER@EXAMPLE.COM",  # uppercase
    ],
)
def test_email_variations(value):
    assert _filter_message(value) == "<email>"
