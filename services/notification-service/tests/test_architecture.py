"""Architecture and boundary integrity tests (CP6.3 Tests 39-43)."""
import inspect
from fastapi.testclient import TestClient

from app.services.alert_rule_engine import AlertRuleEngine
from app.services.alert_lifecycle_service import AlertLifecycleService
from app.schemas.canonical import Alert, Notification


def _get_all_app_routes(app):
    routes = []
    for r in app.routes:
        if hasattr(r, "original_router"):
            for sr in r.original_router.routes:
                routes.append(sr)
        elif hasattr(r, "path"):
            routes.append(r)
    return routes


def test_39_alert_rule_engine_does_not_import_fastapi_or_websocket():
    engine_module = inspect.getmodule(AlertRuleEngine)
    assert engine_module is not None
    source = inspect.getsource(engine_module)
    assert "fastapi" not in source.lower()
    assert "websocket" not in source.lower()
    assert "starlette" not in source.lower()


def test_40_lifecycle_service_does_not_import_transport_layer():
    lifecycle_module = inspect.getmodule(AlertLifecycleService)
    assert lifecycle_module is not None
    source = inspect.getsource(lifecycle_module)
    assert "fastapi" not in source.lower()
    assert "websocket" not in source.lower()
    assert "starlette" not in source.lower()


def test_41_no_duplicate_transport_specific_alert_model(client: TestClient):
    from app.main import app

    routes = _get_all_app_routes(app)
    alert_route = next(
        r for r in routes
        if getattr(r, "path", None) == "/api/v1/alerts" and "GET" in getattr(r, "methods", set())
    )
    # response_model is List[Alert]
    assert alert_route.response_model is not None
    assert "Alert" in str(alert_route.response_model)


def test_42_no_duplicate_transport_specific_notification_model(client: TestClient):
    from app.main import app

    routes = _get_all_app_routes(app)
    notif_route = next(
        r for r in routes
        if getattr(r, "path", None) == "/api/v1/notifications" and "GET" in getattr(r, "methods", set())
    )
    assert notif_route.response_model is not None
    assert "Notification" in str(notif_route.response_model)


def test_43_internal_event_routes_absent_from_openapi(client: TestClient):
    from app.main import app

    openapi_spec = app.openapi()
    paths = openapi_spec.get("paths", {})

    # Ensure /internal/v1/events routes are hidden from public documentation
    for path in paths.keys():
        assert not path.startswith("/internal"), f"Internal route '{path}' leaked into public OpenAPI documentation!"

    # Ensure canonical endpoints are present
    assert "/health" in paths
    assert "/api/v1/alerts" in paths
    assert "/api/v1/alerts/{alertId}" in paths
    assert "/api/v1/alerts/{alertId}/acknowledge" in paths
    assert "/api/v1/alerts/{alertId}/resolve" in paths
    assert "/api/v1/notifications" in paths
    assert "/api/v1/notifications/{notificationId}/read" in paths
    assert "/api/v1/notifications/read-all" in paths
    assert "/api/v1/devices" in paths
    assert "/api/v1/devices/{deviceRegistrationId}" in paths


def test_44_no_firebase_admin_in_domain_ports_services_schemas_repositories():
    """Ensure firebase_admin is strictly encapsulated within app/infrastructure/firebase."""
    import pathlib
    base_dir = pathlib.Path(__file__).parent.parent / "app"
    forbidden_dirs = ["domain", "schemas", "ports", "services", "repositories"]
    for subdir in forbidden_dirs:
        target_dir = base_dir / subdir
        for py_file in target_dir.rglob("*.py"):
            content = py_file.read_text(encoding="utf-8")
            assert "firebase_admin" not in content, f"Forbidden firebase_admin import found in {py_file}!"

