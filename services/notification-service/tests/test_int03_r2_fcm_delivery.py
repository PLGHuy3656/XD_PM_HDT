"""INT03-R2: Targeted Notification Service unit tests for FCM delivery & security."""
import sys
import types
import pytest

from app import delivery, repositories
from app.config import settings


def _sample_notification(link="/owner/farms?requestId=req-1"):
    return {
        "id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        "event_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        "user_id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
        "event_type": "management.inspection_request.status_changed",
        "title": "Cập nhật yêu cầu kiểm tra",
        "message": "Yêu cầu IR-123 đã hoàn thành.",
        "category": "info",
        "data": {"link": link} if link is not None else {},
    }


def test_safe_relative_link_rejects_external_and_protocol_relative_urls():
    assert delivery._safe_relative_link(_sample_notification("/owner/farms")) == "/owner/farms"
    assert delivery._safe_relative_link(_sample_notification("https://evil.example/phish")).startswith("/notifications?id=")
    assert delivery._safe_relative_link(_sample_notification("//evil.example/phish")).startswith("/notifications?id=")
    assert delivery._safe_relative_link(_sample_notification(None)).startswith("/notifications?id=")


def test_send_fcm_skips_when_unconfigured(monkeypatch):
    monkeypatch.setattr(settings, "firebase_service_account_path", "")
    assert delivery.send_fcm(_sample_notification(), "cccccccc-cccc-cccc-cccc-cccccccccccc") is False


def test_send_fcm_skips_when_service_account_file_missing(monkeypatch):
    monkeypatch.setattr(settings, "firebase_service_account_path", "/nonexistent/sa.json")
    assert delivery.send_fcm(_sample_notification(), "cccccccc-cccc-cccc-cccc-cccccccccccc") is False


def test_send_fcm_sends_data_only_payload_and_cleans_unregistered_token(monkeypatch, tmp_path):
    sa_file = tmp_path / "sa.json"
    sa_file.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(settings, "firebase_service_account_path", str(sa_file))
    monkeypatch.setattr(settings, "firebase_project_id", "demo-project")

    sent_messages = []
    deleted_tokens = []

    class FakeUnregisteredError(Exception):
        pass

    class FakeInvalidArgumentError(Exception):
        pass

    class FakeMessage:
        def __init__(self, *, data=None, token=None, notification=None):
            self.data = data
            self.token = token
            self.notification = notification

    fake_messaging = types.SimpleNamespace(
        Message=FakeMessage,
        UnregisteredError=FakeUnregisteredError,
        SenderIdMismatchError=type("FakeSenderIdMismatchError", (Exception,), {}),
        send=lambda msg, app=None: (
            (_ for _ in ()).throw(FakeUnregisteredError("stale"))
            if msg.token == "tok-stale"
            else sent_messages.append(msg)
        ),
    )
    fake_exceptions = types.SimpleNamespace(InvalidArgumentError=FakeInvalidArgumentError)
    fake_credentials = types.SimpleNamespace(Certificate=lambda p: {"path": p})
    fake_firebase_admin = types.SimpleNamespace(
        get_app=lambda name: "fake-app",
        initialize_app=lambda cred, options=None, name=None: "fake-app",
        credentials=fake_credentials,
        exceptions=fake_exceptions,
        messaging=fake_messaging,
    )

    monkeypatch.setitem(sys.modules, "firebase_admin", fake_firebase_admin)
    monkeypatch.setitem(sys.modules, "firebase_admin.credentials", fake_credentials)
    monkeypatch.setitem(sys.modules, "firebase_admin.exceptions", fake_exceptions)
    monkeypatch.setitem(sys.modules, "firebase_admin.messaging", fake_messaging)
    monkeypatch.setattr(repositories, "get_fcm_tokens", lambda uid: ["tok-valid", "tok-stale"])
    monkeypatch.setattr(repositories, "delete_fcm_token", lambda uid, tok: deleted_tokens.append((uid, tok)))

    ok = delivery.send_fcm(_sample_notification("https://evil.example"), "cccccccc-cccc-cccc-cccc-cccccccccccc")
    assert ok is True
    assert len(sent_messages) == 1
    msg = sent_messages[0]
    assert msg.notification is None  # data-only prevents duplicate display
    assert msg.data["notification_id"] == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    assert msg.data["event_id"] == "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    assert msg.data["title"] == "Cập nhật yêu cầu kiểm tra"
    assert msg.data["link"] == "/notifications?id=aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    assert deleted_tokens == [("cccccccc-cccc-cccc-cccc-cccccccccccc", "tok-stale")]


def test_send_fcm_raises_on_transient_error_for_worker_retry(monkeypatch, tmp_path):
    sa_file = tmp_path / "sa.json"
    sa_file.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(settings, "firebase_service_account_path", str(sa_file))

    class FakeMessage:
        def __init__(self, *, data=None, token=None):
            self.data = data
            self.token = token

    fake_messaging = types.SimpleNamespace(
        Message=FakeMessage,
        UnregisteredError=type("FakeUnregisteredError", (Exception,), {}),
        SenderIdMismatchError=type("FakeSenderIdMismatchError", (Exception,), {}),
        send=lambda msg, app=None: (_ for _ in ()).throw(ConnectionError("fcm unavailable")),
    )
    fake_exceptions = types.SimpleNamespace(InvalidArgumentError=type("FakeInvalidArg", (Exception,), {}))
    fake_credentials = types.SimpleNamespace(Certificate=lambda p: {"path": p})
    fake_firebase_admin = types.SimpleNamespace(
        get_app=lambda name: "fake-app",
        initialize_app=lambda cred, options=None, name=None: "fake-app",
        credentials=fake_credentials,
        exceptions=fake_exceptions,
        messaging=fake_messaging,
    )
    monkeypatch.setitem(sys.modules, "firebase_admin", fake_firebase_admin)
    monkeypatch.setitem(sys.modules, "firebase_admin.credentials", fake_credentials)
    monkeypatch.setitem(sys.modules, "firebase_admin.exceptions", fake_exceptions)
    monkeypatch.setitem(sys.modules, "firebase_admin.messaging", fake_messaging)
    monkeypatch.setattr(repositories, "get_fcm_tokens", lambda uid: ["tok-1"])

    with pytest.raises(RuntimeError, match="FCM failed"):
        delivery.send_fcm(_sample_notification(), "cccccccc-cccc-cccc-cccc-cccccccccccc")
