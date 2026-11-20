"""Shared pytest fixtures for IoT Service tests (INT01-R1).

The IoT HTTP/WS API now requires the internal service key (app.security). Pre-existing
tests exercise business logic through TestClient without that key, so this fixture
disables the auth requirement for them (several test modules clear
``app.dependency_overrides`` themselves, so a settings toggle is used instead).
Tests that verify authentication itself are marked ``@pytest.mark.internal_auth`` and
run against the real, enforced check.
"""
import pytest

from app.config import settings


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "internal_auth: run against the real IoT internal service authentication"
    )


@pytest.fixture(autouse=True)
def _bypass_internal_auth_for_business_tests(request, monkeypatch):
    if request.node.get_closest_marker("internal_auth"):
        monkeypatch.setattr(settings, "internal_api_auth_required", True)
    else:
        monkeypatch.setattr(settings, "internal_api_auth_required", False)
    yield
