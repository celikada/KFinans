"""Web Push servisi (app/services/push.py) saf birim testleri (DB'siz).

pywebpush.webpush gerçek ağ çağrısı yapmasın diye mock'lanır. DB'ye dokunan
send_to_user testleri integration/test_push_api.py içinde (tablo + truncate
fixture'larına ihtiyaç duyar).
"""

import uuid
from types import SimpleNamespace

import pytest

from app.services import push as push_service


def _make_settings(public="pub", private="priv", subject="mailto:test@example.com"):
    return SimpleNamespace(
        vapid_public_key=public,
        vapid_private_key=private,
        vapid_subject=subject,
    )


def test_send_web_push_calls_webpush(monkeypatch):
    captured = {}

    def _fake_webpush(*, subscription_info, data, vapid_private_key, vapid_claims):
        captured["sub"] = subscription_info
        captured["data"] = data
        captured["priv"] = vapid_private_key
        captured["claims"] = vapid_claims

    monkeypatch.setattr(push_service, "webpush", _fake_webpush)
    sub = {"endpoint": "https://push/abc", "keys": {"p256dh": "p", "auth": "a"}}
    payload = {"title": "T", "body": "B", "url": "/x", "tag": None}

    result = push_service.send_web_push(sub, payload, _make_settings())

    assert result is True
    assert captured["sub"]["endpoint"] == "https://push/abc"
    assert captured["sub"]["keys"] == {"p256dh": "p", "auth": "a"}
    assert captured["priv"] == "priv"
    assert captured["claims"] == {"sub": "mailto:test@example.com"}
    assert '"title": "T"' in captured["data"]


@pytest.mark.asyncio
async def test_send_to_user_noop_without_vapid():
    """VAPID anahtarı boşsa hiç gönderim yapılmaz (0 döner, DB'ye dokunmaz)."""

    class _DummyDB:
        async def execute(self, *_a, **_k):  # pragma: no cover - çağrılmamalı
            raise AssertionError("VAPID yokken DB sorgusu yapılmamalı")

    sent = await push_service.send_to_user(
        _DummyDB(),
        uuid.uuid4(),
        title="T",
        body="B",
        url="/x",
        app_settings=_make_settings(public="", private=""),
    )
    assert sent == 0
