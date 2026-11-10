"""
Comprehensive Integration Tests for Analytics Data Pipeline.

Tests:
1. PG-01 Management Sync: Syncs real dimensions (farms, zones, devices) from management_db.
2. PG-02 IoT Telemetry Sync: Hourly sample-weighted rollups with NULL preservation.
3. PG-03 AI Counts Sync: Atomic deduplication ledger & deterministic snapshot materialization.
4. PG-04 Notification Alerts Sync: Hourly severity rollups.
5. Idempotent Replay: Re-running pipeline causes zero metric drift or double counting.
6. Repository End-to-End: Verifies PostgreSQL repository reads synchronized dimensions.
"""
import os
from datetime import datetime, timedelta, timezone
import pytest
import psycopg
from psycopg.conninfo import make_conninfo

from app.domain.enums import PeriodEnum
from app.pipeline.pipeline_runner import AnalyticsPipelineRunner
from app.repositories.postgresql_repository import PostgreSQLAnalyticsRepository


def _resolve_admin_conninfo(dbname: str) -> str:
    """Helper to connect as admin for seeding/cleaning synthetic test fixtures."""
    host = os.getenv("PGHOST", "127.0.0.1")
    port = int(os.getenv("PGPORT", "5432"))
    user = os.getenv("PGUSER", "postgres")
    pw = os.getenv("PGPASSWORD", "263656")
    return make_conninfo(host=host, port=port, user=user, password=pw, dbname=dbname)


@pytest.fixture(scope="session")
def pipeline_runner():
    """Provides pipeline runner connected to local test/official databases."""
    return AnalyticsPipelineRunner()


def test_pg01_dimension_synchronization(pipeline_runner):
    """
    Validates synchronization of real seeded farms, zones, and devices
    from management_db to analytics_db.
    """
    counts = pipeline_runner.sync_dimensions()
    print(f"\n[PG-01 Dimension Sync Result] {counts}")
    assert counts["farms"] >= 2, f"Expected >= 2 farms, got {counts['farms']}"
    assert counts["zones"] >= 3, f"Expected >= 3 zones, got {counts['zones']}"
    assert counts["devices"] >= 2, f"Expected >= 2 devices, got {counts['devices']}"

    # Verify directly in analytics_db
    with psycopg.connect(pipeline_runner.analytics_db_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM dim_farms;")
            f_count = cur.fetchone()[0]
            assert f_count >= 2

            cur.execute("SELECT count(*) FROM dim_zones;")
            z_count = cur.fetchone()[0]
            assert z_count >= 3

            cur.execute("SELECT count(*) FROM dim_devices;")
            d_count = cur.fetchone()[0]
            assert d_count >= 2


def test_pg03_ai_counts_atomic_ledger_and_rollup(pipeline_runner):
    """
    Validates atomic ledger deduplication and deterministic 2-stage rollup.
    Inserts sample count update and checks ledger, staging, and fact tables.
    """
    now = datetime.now(timezone.utc)
    t_bucket = now.replace(minute=0, second=0, microsecond=0)
    test_cam = "cam-pipeline-test-01"
    frame_id = 1001

    # Pre-clean staging & fact tables in analytics_db and ai_db
    with psycopg.connect(pipeline_runner.analytics_db_url) as ana_conn:
        with ana_conn.cursor() as cur:
            cur.execute("DELETE FROM fact_bird_activity_hourly WHERE camera_id = %s;", (test_cam,))
            cur.execute("DELETE FROM stg_count_updates WHERE camera_id = %s;", (test_cam,))
            cur.execute("DELETE FROM stg_event_dedup_ledger WHERE source_subsystem = 'AI_COUNT';")
        ana_conn.commit()

    with psycopg.connect(_resolve_admin_conninfo("ai_db")) as ai_conn:
        with ai_conn.cursor() as cur:
            cur.execute("DELETE FROM ai_count_updates WHERE camera_id = %s;", (test_cam,))
            cur.execute(
                """
                INSERT INTO ai_count_updates
                (camera_id, farm_id, zone_id, frame_id, entry_count, exit_count, net_change, delta_entry, delta_exit, window_started_at, recorded_at)
                VALUES
                (%s, 'a18d8eee-cb1a-4b00-b375-d505eb8128d7', '7122bcb8-9ce9-46bc-a640-a1060788b809', %s, 10, 4, 6, 10, 4, %s, %s);
                """,
                (test_cam, frame_id, now - timedelta(seconds=10), now),
            )
        ai_conn.commit()

    # 2. Run AI sync 1st time
    stats1 = pipeline_runner.sync_ai_counts()
    print(f"\n[PG-03 Run 1] {stats1}")
    assert stats1["ingested_staging"] >= 1
    assert stats1["materialized_buckets"] >= 1

    # 3. Run AI sync 2nd time (Replay / Idempotency check)
    stats2 = pipeline_runner.sync_ai_counts()
    print(f"[PG-03 Run 2 (Replay)] {stats2}")
    # Duplicate records must be caught by deduplication ledger
    assert stats2["deduped"] >= 1

    # 4. Verify fact_bird_activity_hourly has exact net change (10 - 4 = 6)
    with psycopg.connect(pipeline_runner.analytics_db_url) as ana_conn:
        with ana_conn.cursor() as cur:
            cur.execute(
                """
                SELECT entries, exits, net_change
                FROM fact_bird_activity_hourly
                WHERE camera_id = %s;
                """,
                (test_cam,),
            )
            row = cur.fetchone()
            assert row is not None
            assert row[0] == 10
            assert row[1] == 4
            assert row[2] == 6

    # 5. Cleanup test event from ai_db and analytics_db
    with psycopg.connect(_resolve_admin_conninfo("ai_db")) as ai_conn:
        with ai_conn.cursor() as cur:
            cur.execute("DELETE FROM ai_count_updates WHERE camera_id = %s;", (test_cam,))
        ai_conn.commit()

    with psycopg.connect(pipeline_runner.analytics_db_url) as ana_conn:
        with ana_conn.cursor() as cur:
            cur.execute("DELETE FROM fact_bird_activity_hourly WHERE camera_id = %s;", (test_cam,))
            cur.execute("DELETE FROM stg_count_updates WHERE camera_id = %s;", (test_cam,))
            cur.execute("DELETE FROM stg_event_dedup_ledger WHERE source_subsystem = 'AI_COUNT';")
        ana_conn.commit()


def test_pg02_iot_telemetry_rollup(pipeline_runner):
    """
    Validates IoT telemetry hourly rollup with sample-weighted averaging.
    """
    now = datetime.now(timezone.utc)
    t_bucket = now.replace(minute=0, second=0, microsecond=0)
    test_node = "SWC-DEMO-NODE-001"

    # Pre-clean test records in iot_db and analytics_db
    with psycopg.connect(_resolve_admin_conninfo("iot_db")) as iot_conn:
        with iot_conn.cursor() as cur:
            cur.execute("DELETE FROM telemetry_records WHERE device_id = %s;", (test_node,))
        iot_conn.commit()

    with psycopg.connect(pipeline_runner.analytics_db_url) as ana_conn:
        with ana_conn.cursor() as cur:
            cur.execute("DELETE FROM fact_telemetry_hourly WHERE device_id = %s;", (test_node,))
        ana_conn.commit()

    # Seed 2 raw telemetry rows in iot_db
    with psycopg.connect(_resolve_admin_conninfo("iot_db")) as iot_conn:
        with iot_conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO telemetry_records
                (device_id, farm_id, zone_id, temperature, humidity, lux, co2, audio_rms, audio_healthy, misting, fan, heater, alarm, mode, received_at, recorded_at)
                VALUES
                (%s, 'a18d8eee-cb1a-4b00-b375-d505eb8128d7', '7122bcb8-9ce9-46bc-a640-a1060788b809', 28.0, 80.0, 10.0, 500.0, 45.0, TRUE, FALSE, TRUE, FALSE, FALSE, 'AUTO', %s, %s),
                (%s, 'a18d8eee-cb1a-4b00-b375-d505eb8128d7', '7122bcb8-9ce9-46bc-a640-a1060788b809', 30.0, 84.0, 10.0, 520.0, 45.0, TRUE, FALSE, TRUE, FALSE, FALSE, 'AUTO', %s, %s);
                """,
                (test_node, now, now, test_node, now, now),
            )
        iot_conn.commit()

    # Run IoT sync
    stats = pipeline_runner.sync_iot_telemetry()
    print(f"\n[PG-02 IoT Sync Result] {stats}")
    assert stats["rollups_updated"] >= 1

    # Verify fact_telemetry_hourly has average temperature = (28.0 + 30.0) / 2 = 29.0
    with psycopg.connect(pipeline_runner.analytics_db_url) as ana_conn:
        with ana_conn.cursor() as cur:
            cur.execute(
                """
                SELECT avg_temperature, min_temperature, max_temperature, avg_humidity, sample_count
                FROM fact_telemetry_hourly
                WHERE device_id = %s AND time_bucket = %s;
                """,
                (test_node, t_bucket),
            )
            row = cur.fetchone()
            assert row is not None
            assert row[0] == 29.0
            assert row[1] == 28.0
            assert row[2] == 30.0
            assert row[3] == 82.0
            assert row[4] == 2

    # Cleanup iot_db and analytics_db test rows
    with psycopg.connect(_resolve_admin_conninfo("iot_db")) as iot_conn:
        with iot_conn.cursor() as cur:
            cur.execute("DELETE FROM telemetry_records WHERE device_id = %s;", (test_node,))
        iot_conn.commit()

    with psycopg.connect(pipeline_runner.analytics_db_url) as ana_conn:
        with ana_conn.cursor() as cur:
            cur.execute("DELETE FROM fact_telemetry_hourly WHERE device_id = %s;", (test_node,))
        ana_conn.commit()


def test_pg04_alerts_rollup(pipeline_runner):
    """
    Validates operational alerts aggregation into fact_alerts_hourly.
    """
    now = datetime.now(timezone.utc)
    t_alert_id = "alert-pipeline-test-01"

    # Seed alert in notification_db
    with psycopg.connect(_resolve_admin_conninfo("notification_db")) as notif_conn:
        with notif_conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO alerts
                (alert_id, event_type, source, severity, status, farm_id, zone_id, title, message, created_at, updated_at)
                VALUES
                (%s, 'HIGH_TEMPERATURE', 'IOT_ENVIRONMENT', 'CRITICAL', 'OPEN', 'a18d8eee-cb1a-4b00-b375-d505eb8128d7', '7122bcb8-9ce9-46bc-a640-a1060788b809', 'Nhiệt độ quá cao', 'Cảnh báo nhiệt độ', %s, %s);
                """,
                (t_alert_id, now, now),
            )
        notif_conn.commit()

    # Run Alert sync
    stats = pipeline_runner.sync_alerts()
    print(f"\n[PG-04 Alerts Sync Result] {stats}")
    assert stats["alert_rollups_updated"] >= 1

    # Verify fact_alerts_hourly
    with psycopg.connect(pipeline_runner.analytics_db_url) as ana_conn:
        with ana_conn.cursor() as cur:
            cur.execute(
                """
                SELECT critical_count, total_count
                FROM fact_alerts_hourly
                WHERE farm_id = 'a18d8eee-cb1a-4b00-b375-d505eb8128d7'
                  AND zone_id = '7122bcb8-9ce9-46bc-a640-a1060788b809';
                """
            )
            row = cur.fetchone()
            assert row is not None
            assert row[0] >= 1
            assert row[1] >= 1

    # Cleanup notification_db and analytics_db
    with psycopg.connect(_resolve_admin_conninfo("notification_db")) as notif_conn:
        with notif_conn.cursor() as cur:
            cur.execute("DELETE FROM alerts WHERE alert_id = %s;", (t_alert_id,))
        notif_conn.commit()

    with psycopg.connect(pipeline_runner.analytics_db_url) as ana_conn:
        with ana_conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM fact_alerts_hourly
                WHERE farm_id = 'a18d8eee-cb1a-4b00-b375-d505eb8128d7'
                  AND zone_id = '7122bcb8-9ce9-46bc-a640-a1060788b809'
                  AND time_bucket >= %s;
                """,
                (now - timedelta(hours=1),),
            )
        ana_conn.commit()


@pytest.mark.anyio
async def test_repository_e2e_reads_synced_dimensions(pipeline_runner):
    """
    Verifies that PostgreSQLAnalyticsRepository reads the synchronized dimensions from analytics_db.
    """
    repo = PostgreSQLAnalyticsRepository(database_url=pipeline_runner.analytics_db_url)
    meta = await repo.get_farm_metadata("a18d8eee-cb1a-4b00-b375-d505eb8128d7")
    assert meta is not None
    assert meta["id"] == "a18d8eee-cb1a-4b00-b375-d505eb8128d7"
    assert "Nhà yến Demo 01" in meta["name"]
    assert len(meta["zones"]) == 2
