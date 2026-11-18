"""
Comprehensive Parity & Integration Tests for PostgreSQL Analytics Repository.

Tests:
1. Interface Parity: Validates signature and method compatibility with IAnalyticsRepository.
2. Isolated Database Integration: Uses analytics_schema_test_db (NEVER writes to official analytics_db).
3. Edge Cases: Empty fact tables, NULL telemetry, data gaps, timezone handling.
4. Security: SQL injection resistance via parameterized queries.
5. Reliability: Connection timeout and lifecycle cleanup.
"""
import os
import inspect
from datetime import datetime, timezone
import pytest
import psycopg
from psycopg.conninfo import make_conninfo
from fastapi.testclient import TestClient

from app.domain.enums import AlertSeverity, MetricType, PeriodEnum
from app.domain.models import BirdActivityBucket
from app.ports.analytics_repository import IAnalyticsRepository
from app.repositories.in_memory_repository import InMemoryAnalyticsRepository
from app.repositories.postgresql_repository import PostgreSQLAnalyticsRepository
from app.services.analytics_service import AnalyticsService, FarmNotFoundError
from app.main import app
from app.api.deps import get_analytics_repository


def _resolve_test_db_conninfo() -> str:
    """Dynamically resolves test db connection string via standard libpq parameters."""
    direct = os.getenv("ANALYTICS_TEST_DATABASE_URL")
    if direct:
        return direct
    host = os.getenv("PGHOST", "127.0.0.1")
    port = int(os.getenv("PGPORT", "5432"))
    user = os.getenv("PGUSER", "postgres")
    pw = os.getenv("PGPASSWORD", "263656")
    db = os.getenv("PGTESTDB", "analytics_schema_test_db")
    return make_conninfo(host=host, port=port, user=user, password=pw, dbname=db)


TEST_DB_URL = _resolve_test_db_conninfo()


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------
@pytest.fixture(scope="session")
def pg_repo():
    """Provides PostgreSQL repository pointed strictly to test database."""
    return PostgreSQLAnalyticsRepository(database_url=TEST_DB_URL, timeout_seconds=3.0)


@pytest.fixture(scope="session", autouse=True)
def setup_test_data(pg_repo):
    """
    Seeds synthetic test fixtures into analytics_schema_test_db.
    Zero interaction with official analytics_db.
    """
    now = datetime.now(timezone.utc)
    t1 = now.replace(minute=0, second=0, microsecond=0)

    with pg_repo._get_connection() as conn:
        with conn.cursor() as cur:
            # Clean test tables in test db
            cur.execute("""
                TRUNCATE TABLE fact_harvest_yield, fact_alerts_hourly,
                               fact_bird_activity_hourly, fact_telemetry_hourly,
                               stg_count_updates, stg_event_dedup_ledger,
                               dim_devices, dim_zones, dim_farms CASCADE;
            """)

            # Seed Dimensions
            cur.execute("""
                INSERT INTO dim_farms (farm_id, name, owner_id)
                VALUES ('farm-parity-01', 'Nhà Yến Parity', 'owner-001'),
                       ('farm-parity-empty', 'Nhà Yến Trống Dữ Liệu', 'owner-002');
            """)
            cur.execute("""
                INSERT INTO dim_zones (zone_id, farm_id, name)
                VALUES ('zone-p-1', 'farm-parity-01', 'Khu A Cửa Chính'),
                       ('zone-p-2', 'farm-parity-01', 'Khu B Tầng 2');
            """)
            cur.execute("""
                INSERT INTO dim_devices (device_id, farm_id, zone_id, status)
                VALUES ('dev-p-01', 'farm-parity-01', 'zone-p-1', 'ACTIVE'),
                       ('dev-p-02', 'farm-parity-01', 'zone-p-2', 'ACTIVE');
            """)

            # Seed fact_bird_activity_hourly
            cur.execute("""
                INSERT INTO fact_bird_activity_hourly
                (farm_id, zone_id, camera_id, time_bucket, entries, exits, net_change, is_coverage_healthy)
                VALUES
                ('farm-parity-01', 'zone-p-1', 'cam-01', %s, 150, 120, 30, TRUE);
            """, (t1,))

            # Seed fact_telemetry_hourly (Zone 1 has data, Zone 2 has partial NULL)
            cur.execute("""
                INSERT INTO fact_telemetry_hourly
                (farm_id, zone_id, device_id, time_bucket, avg_temperature, avg_humidity, avg_co2, sample_count, has_data_gaps)
                VALUES
                ('farm-parity-01', 'zone-p-1', 'dev-p-01', %s, 28.5, 82.0, 510.0, 60, FALSE),
                ('farm-parity-01', 'zone-p-2', 'dev-p-02', %s, NULL, 80.0, NULL, 30, TRUE);
            """, (t1, t1))

            # Seed fact_alerts_hourly
            cur.execute("""
                INSERT INTO fact_alerts_hourly
                (farm_id, zone_id, time_bucket, critical_count, high_count, medium_count, low_count, total_count)
                VALUES
                ('farm-parity-01', 'GLOBAL', %s, 1, 2, 3, 0, 6);
            """, (t1,))

            # Seed fact_harvest_yield
            cur.execute("""
                INSERT INTO fact_harvest_yield
                (harvest_id, farm_id, zone_id, harvest_date, total_nests, harvested_nests, yield_kg)
                VALUES
                ('harv-p-01', 'farm-parity-01', 'zone-p-1', %s, 500, 150, 1.45);
            """, (t1.date(),))

        conn.commit()


# -----------------------------------------------------------------------------
# 1. Interface Parity Tests
# -----------------------------------------------------------------------------
def test_interface_parity():
    """Validates that PostgreSQL repository implements 100% of IAnalyticsRepository interface."""
    assert issubclass(PostgreSQLAnalyticsRepository, IAnalyticsRepository)

    expected_methods = {
        "get_farm_metadata",
        "get_bird_activity_buckets",
        "get_zone_climate_averages",
        "get_alerts",
        "get_yield_data",
        "get_trends_data",
    }

    in_mem_methods = {m for m, _ in inspect.getmembers(InMemoryAnalyticsRepository, predicate=inspect.isfunction) if not m.startswith("_")}
    pg_methods = {m for m, _ in inspect.getmembers(PostgreSQLAnalyticsRepository, predicate=inspect.isfunction) if not m.startswith("_")}

    assert expected_methods.issubset(in_mem_methods)
    assert expected_methods.issubset(pg_methods)


# -----------------------------------------------------------------------------
# 2. Metadata & Farm Existence Tests
# -----------------------------------------------------------------------------
@pytest.mark.anyio
async def test_get_farm_metadata(pg_repo):
    """Tests metadata query for valid and non-existent farms."""
    meta = await pg_repo.get_farm_metadata("farm-parity-01")
    assert meta is not None
    assert meta["id"] == "farm-parity-01"
    assert meta["name"] == "Nhà Yến Parity"
    assert len(meta["zones"]) == 2

    # Non-existent farm
    missing = await pg_repo.get_farm_metadata("non-existent-farm-999")
    assert missing is None


# -----------------------------------------------------------------------------
# 3. Bird Activity & Calculations
# -----------------------------------------------------------------------------
@pytest.mark.anyio
async def test_get_bird_activity_buckets(pg_repo):
    """Tests retrieval of bird activity buckets from PostgreSQL."""
    buckets, prev_entries, coverage = await pg_repo.get_bird_activity_buckets("farm-parity-01", PeriodEnum.DAY)
    assert len(buckets) >= 1
    b = buckets[0]
    assert b.entries == 150
    assert b.exits == 120
    assert b.net_flux == 30

    # Empty farm should return empty bucket list
    empty_b, _, _ = await pg_repo.get_bird_activity_buckets("farm-parity-empty", PeriodEnum.DAY)
    assert empty_b == []


# -----------------------------------------------------------------------------
# 4. Microclimate NULL Safety & Data Gaps
# -----------------------------------------------------------------------------
@pytest.mark.anyio
async def test_get_zone_climate_averages_null_safety(pg_repo):
    """Validates that missing sensor values are returned as None, never 0.0."""
    climates = await pg_repo.get_zone_climate_averages("farm-parity-01", PeriodEnum.DAY)
    assert len(climates) == 2

    z1 = next(c for c in climates if c["zone_id"] == "zone-p-1")
    assert z1["avg_temperature"] == 28.5
    assert z1["avg_humidity"] == 82.0
    assert z1["avg_co2"] == 510.0

    z2 = next(c for c in climates if c["zone_id"] == "zone-p-2")
    assert z2["avg_temperature"] is None  # Sensor offline preserved
    assert z2["avg_humidity"] == 80.0
    assert z2["avg_co2"] is None


# -----------------------------------------------------------------------------
# 5. Alerts & Harvest Yield
# -----------------------------------------------------------------------------
@pytest.mark.anyio
async def test_get_alerts_and_yield(pg_repo):
    """Tests alert severity mappings and harvest yield data."""
    alerts = await pg_repo.get_alerts("farm-parity-01", PeriodEnum.DAY)
    assert alerts.count(AlertSeverity.CRITICAL) == 1
    assert alerts.count(AlertSeverity.HIGH) == 2
    assert alerts.count(AlertSeverity.MEDIUM) == 3

    y_data = await pg_repo.get_yield_data("farm-parity-01", PeriodEnum.DAY)
    assert y_data is not None
    assert y_data["total_nests"] == 500
    assert y_data["harvested_nests"] == 150
    assert y_data["current_yield"] == 1.45


# -----------------------------------------------------------------------------
# 6. Full Service Integration (Summary & Trends DTOs)
# -----------------------------------------------------------------------------
@pytest.mark.anyio
async def test_analytics_service_with_postgres(pg_repo):
    """Tests AnalyticsService orchestration with PostgreSQL repository."""
    svc = AnalyticsService(repository=pg_repo)

    # 6.1 Farm Summary Response
    summary = await svc.get_farm_summary("farm-parity-01", period_str="day")
    assert summary.farmId == "farm-parity-01"
    assert summary.birdPerformance.entries == 150
    assert summary.birdPerformance.exits == 120
    assert summary.birdPerformance.difference == 30
    assert summary.yieldSummary is not None
    assert summary.yieldSummary.totalNests == 500
    assert summary.yieldSummary.currentYield == 1.45

    # 6.2 Trends Response
    trends = await svc.get_trends(farm_id="farm-parity-01", period_str="today")
    assert trends.farmId == "farm-parity-01"
    assert len(trends.hourlyBirdActivity) >= 1
    assert trends.hourlyBirdActivity[0].entries == 150

    # 6.3 Non-existent farm throws FarmNotFoundError
    with pytest.raises(FarmNotFoundError):
        await svc.get_farm_summary("invalid-farm-id", period_str="day")


# -----------------------------------------------------------------------------
# 7. SQL Injection Resistance
# -----------------------------------------------------------------------------
@pytest.mark.anyio
async def test_sql_injection_resistance(pg_repo):
    """Validates that SQL injection attempts are safely parameterized."""
    malicious_inputs = [
        "farm-parity-01' OR '1'='1",
        "'; DROP TABLE dim_farms; --",
        "1; SELECT pg_sleep(5); --",
    ]
    for injection in malicious_inputs:
        meta = await pg_repo.get_farm_metadata(injection)
        assert meta is None, f"Injection input '{injection}' should return None"


# -----------------------------------------------------------------------------
# 8. Connection Error & Timeout Handling
# -----------------------------------------------------------------------------
@pytest.mark.anyio
async def test_connection_timeout_and_error():
    """Validates that connection error raises cleanly without unhandled crash."""
    dummy_pw = "invalid_" + "pwd"
    bad_conninfo = make_conninfo(host="127.0.0.1", port=5432, user="invalid_usr", password=dummy_pw, dbname="analytics_db")
    unreachable_repo = PostgreSQLAnalyticsRepository(
        database_url=bad_conninfo,
        timeout_seconds=1.0,
    )
    with pytest.raises(Exception):
        await unreachable_repo.get_farm_metadata("farm-parity-01")


# -----------------------------------------------------------------------------
# 9. FastAPI Controller Integration with PostgreSQL Adapter
# -----------------------------------------------------------------------------
def test_fastapi_endpoints_with_postgres_repo(pg_repo):
    """Tests FastAPI HTTP endpoint execution using dependency override for PostgreSQL repo."""
    app.dependency_overrides[get_analytics_repository] = lambda: pg_repo
    client = TestClient(app)

    try:
        # GET /summary
        resp_sum = client.get("/api/v1/analytics/farms/farm-parity-01/summary?period=day")
        assert resp_sum.status_code == 200
        data_sum = resp_sum.json()
        assert data_sum["farmId"] == "farm-parity-01"
        assert "birdPerformance" in data_sum
        assert "microClimateScores" in data_sum
        assert "alertDistribution" in data_sum
        assert "yieldSummary" in data_sum

        # GET /trends
        resp_trend = client.get("/api/v1/analytics/farms/farm-parity-01/trends?period=today")
        assert resp_trend.status_code == 200
        data_trend = resp_trend.json()
        assert data_trend["farmId"] == "farm-parity-01"
        assert "hourlyBirdActivity" in data_trend
        assert "environmentComparison" in data_trend

        # 404 for unknown farm
        resp_404 = client.get("/api/v1/analytics/farms/unknown-farm/summary")
        assert resp_404.status_code == 404
        assert resp_404.json()["error"]["code"] == "FARM_NOT_FOUND"

    finally:
        app.dependency_overrides.clear()
