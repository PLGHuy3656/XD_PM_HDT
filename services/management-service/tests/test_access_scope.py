import importlib

from app.repositories.farm_repository import FarmRepository
from app.repositories.device_repository import DeviceRepository
from app.controllers.farm_controller import farm_controller
from app.controllers.device_controller import device_controller
from app.routes.device_routes import list_devices

farm_repository_module = importlib.import_module(
    "app.repositories.farm_repository",
)
device_repository_module = importlib.import_module(
    "app.repositories.device_repository",
)


class FakeCursor:
    def __init__(self):
        self.query = ""
        self.params = ()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def execute(self, query, params=()):
        self.query = query
        self.params = params

    def fetchall(self):
        return []

    def fetchone(self):
        return None


class FakeConnection:
    def __init__(self):
        self.fake_cursor = FakeCursor()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def cursor(self):
        return self.fake_cursor


def test_farm_list_query_scopes_owner_and_technician(monkeypatch):
    connection = FakeConnection()
    monkeypatch.setattr(
        farm_repository_module,
        "get_connection",
        lambda: connection,
    )

    FarmRepository().list_farms(
        user_id="user-01",
        is_admin=False,
        is_owner=True,
        is_technician=True,
    )

    assert "f.owner_id::text = %s" in connection.fake_cursor.query
    assert "ta.technician_id::text = %s" in connection.fake_cursor.query
    assert "ta.is_active = TRUE" in connection.fake_cursor.query
    assert connection.fake_cursor.params == ("user-01", "user-01")


def test_farm_list_query_returns_no_farms_for_unrecognized_role(monkeypatch):
    connection = FakeConnection()
    monkeypatch.setattr(
        farm_repository_module,
        "get_connection",
        lambda: connection,
    )

    FarmRepository().list_farms(
        user_id="user-01",
        is_admin=False,
        is_owner=False,
        is_technician=False,
    )

    assert "WHERE FALSE" in connection.fake_cursor.query


def test_farm_detail_query_has_valid_lateral_join_closure(monkeypatch):
    connection = FakeConnection()
    monkeypatch.setattr(
        farm_repository_module,
        "get_connection",
        lambda: connection,
    )

    FarmRepository().get_farm_by_id("farm-code")

    assert ") AS t ON TRUE" in connection.fake_cursor.query
    assert ") t                 ) AS t" not in connection.fake_cursor.query
    assert "f.id::text = %s" in connection.fake_cursor.query


def test_device_list_empty_scope_does_not_query_database(monkeypatch):
    def unexpected_connection():
        raise AssertionError("Database must not be queried for an empty scope")

    monkeypatch.setattr(
        device_repository_module,
        "get_connection",
        unexpected_connection,
    )

    assert DeviceRepository().list_devices(farm_ids=[]) == []


def test_device_list_query_constrains_accessible_farms(monkeypatch):
    connection = FakeConnection()
    monkeypatch.setattr(
        device_repository_module,
        "get_connection",
        lambda: connection,
    )
    monkeypatch.setattr(
        device_repository_module.legacy_iot_adapter,
        "get_devices_runtime_state",
        lambda device_ids: {},
    )

    DeviceRepository().list_devices(farm_ids=["farm-01", "farm-02"])

    assert "d.farm_id::text = ANY(%s)" in connection.fake_cursor.query
    assert connection.fake_cursor.params == (["farm-01", "farm-02"],)


def test_device_route_scopes_unfiltered_list_to_accessible_farms(monkeypatch):
    current_user = {"id": "tech-01", "roles": ["TECHNICIAN"]}
    captured = {}
    monkeypatch.setattr(
        farm_controller,
        "list_farms",
        lambda user: [
            {"farm_id": "farm-01"},
            {"farm_id": "farm-02"},
        ],
    )
    monkeypatch.setattr(
        device_controller,
        "list_devices",
        lambda **kwargs: captured.update(kwargs) or [],
    )

    result = list_devices(
        farm_id=None,
        zone_id=None,
        current_user=current_user,
    )

    assert result == []
    assert captured["farm_ids"] == ["farm-01", "farm-02"]
