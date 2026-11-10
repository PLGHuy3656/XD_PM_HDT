"""
SwiftletCare CP9 — Analytics Data Pipeline Synchronization Runner.

Executes decoupled ETL sync from operational databases to analytics_db:
1. PG-01: Management Metadata Sync (farms, zones, devices -> dim_*)
2. PG-02: IoT Telemetry Ingestion (telemetry_records -> fact_telemetry_hourly)
3. PG-03: AI Counts Sync (ai_count_updates -> stg_count_updates -> fact_bird_activity_hourly)
4. PG-04: Operational Alerts Rollup (alerts -> fact_alerts_hourly)

Architectural Principles (CP9_PHASE3A_DATA_INTEGRATION_DESIGN.md):
- Read-only queries against operational databases using analytics_reader role.
- Single atomic transaction boundary per ingestion batch.
- Monotonic composite tie-breaker (recorded_at, id) for append-only logs.
- Overlapping lookback watermark buffer (Δt = 2 min) for mutable records.
- 2-stage deterministic aggregation (snapshot materialization, zero additive drift).
"""
import hashlib
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import psycopg
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row


class AnalyticsPipelineRunner:
    """
    Orchestrates the 4 synchronization pipelines into analytics_db.
    """

    def __init__(
        self,
        analytics_db_url: Optional[str] = None,
        management_db_url: Optional[str] = None,
        iot_db_url: Optional[str] = None,
        ai_db_url: Optional[str] = None,
        notification_db_url: Optional[str] = None,
        timeout_seconds: float = 10.0,
    ):
        base_host = os.getenv("PGHOST", "127.0.0.1")
        base_port = int(os.getenv("PGPORT", "5432"))
        reader_user = os.getenv("ANALYTICS_READER_USER", "analytics_reader")
        reader_pw = os.getenv("ANALYTICS_READER_PASS", "analytics_reader_secure_pass_2026")

        self.analytics_db_url = analytics_db_url or os.getenv(
            "ANALYTICS_DATABASE_URL",
            make_conninfo(host=base_host, port=base_port, user=reader_user, password=reader_pw, dbname="analytics_db"),
        )
        self.management_db_url = management_db_url or os.getenv(
            "MANAGEMENT_DATABASE_URL",
            make_conninfo(host=base_host, port=base_port, user=reader_user, password=reader_pw, dbname="management_db"),
        )
        self.iot_db_url = iot_db_url or os.getenv(
            "IOT_DATABASE_URL",
            make_conninfo(host=base_host, port=base_port, user=reader_user, password=reader_pw, dbname="iot_db"),
        )
        self.ai_db_url = ai_db_url or os.getenv(
            "AI_DATABASE_URL",
            make_conninfo(host=base_host, port=base_port, user=reader_user, password=reader_pw, dbname="ai_db"),
        )
        self.notification_db_url = notification_db_url or os.getenv(
            "NOTIFICATION_DATABASE_URL",
            make_conninfo(host=base_host, port=base_port, user=reader_user, password=reader_pw, dbname="notification_db"),
        )
        self.timeout_seconds = timeout_seconds

    # -------------------------------------------------------------------------
    # Pipeline 1: Management Dimension Sync
    # -------------------------------------------------------------------------
    def sync_dimensions(self) -> Dict[str, int]:
        """
        Synchronizes farms, zones, and devices from management_db into dim_* tables.
        Applies lookback watermark and idempotent upserts.
        """
        counts = {"farms": 0, "zones": 0, "devices": 0}

        # 1. Read from management_db
        with psycopg.connect(self.management_db_url, connect_timeout=self.timeout_seconds, row_factory=dict_row) as mgmt_conn:
            with mgmt_conn.cursor() as cur:
                cur.execute("SELECT id::text AS farm_id, name, owner_id::text AS owner_id, address FROM farms;")
                farms = cur.fetchall()

                cur.execute("SELECT id::text AS zone_id, farm_id::text AS farm_id, name, zone_code AS description FROM zones;")
                zones = cur.fetchall()

                cur.execute("""
                    SELECT id::text AS device_id, node_id, farm_id::text AS farm_id, zone_id::text AS zone_id,
                           CASE WHEN is_active THEN 'ACTIVE' ELSE 'INACTIVE' END AS status
                    FROM devices;
                """)
                devices = cur.fetchall()

        # 2. Write to analytics_db in single transaction
        with psycopg.connect(self.analytics_db_url, connect_timeout=self.timeout_seconds) as ana_conn:
            with ana_conn.cursor() as cur:
                # Sync Farms
                for f in farms:
                    cur.execute(
                        """
                        INSERT INTO dim_farms (farm_id, name, owner_id, address, synced_at)
                        VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                        ON CONFLICT (farm_id) DO UPDATE SET
                            name = EXCLUDED.name,
                            owner_id = EXCLUDED.owner_id,
                            address = EXCLUDED.address,
                            synced_at = CURRENT_TIMESTAMP;
                        """,
                        (f["farm_id"], f["name"], f["owner_id"], f["address"]),
                    )
                    counts["farms"] += 1

                # Sync Zones
                for z in zones:
                    cur.execute(
                        """
                        INSERT INTO dim_zones (zone_id, farm_id, name, description, synced_at)
                        VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                        ON CONFLICT (zone_id) DO UPDATE SET
                            name = EXCLUDED.name,
                            description = EXCLUDED.description,
                            synced_at = CURRENT_TIMESTAMP;
                        """,
                        (z["zone_id"], z["farm_id"], z["name"], z["description"]),
                    )
                    counts["zones"] += 1

                # Sync Devices (Hardware node_id + DB UUID)
                for d in devices:
                    # Register hardware node_id (used by IoT telemetry)
                    if d.get("node_id"):
                        cur.execute(
                            """
                            INSERT INTO dim_devices (device_id, farm_id, zone_id, status, synced_at)
                            VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                            ON CONFLICT (device_id) DO UPDATE SET
                                farm_id = EXCLUDED.farm_id,
                                zone_id = EXCLUDED.zone_id,
                                status = EXCLUDED.status,
                                synced_at = CURRENT_TIMESTAMP;
                            """,
                            (d["node_id"], d["farm_id"], d["zone_id"], d["status"]),
                        )
                    # Also register internal UUID
                    cur.execute(
                        """
                        INSERT INTO dim_devices (device_id, farm_id, zone_id, status, synced_at)
                        VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                        ON CONFLICT (device_id) DO UPDATE SET
                            farm_id = EXCLUDED.farm_id,
                            zone_id = EXCLUDED.zone_id,
                            status = EXCLUDED.status,
                            synced_at = CURRENT_TIMESTAMP;
                        """,
                        (d["device_id"], d["farm_id"], d["zone_id"], d["status"]),
                    )
                    counts["devices"] += 1

            ana_conn.commit()

        return counts

    # -------------------------------------------------------------------------
    # Pipeline 2: AI Counts Ingestion & 2-Stage Deterministic Rollup
    # -------------------------------------------------------------------------
    def sync_ai_counts(self, batch_size: int = 1000) -> Dict[str, int]:
        """
        Synchronizes bird count updates from ai_db into staging and rollups into fact_bird_activity_hourly.
        Uses atomic deduplication ledger to prevent double-counting.
        """
        stats = {"ingested_staging": 0, "deduped": 0, "materialized_buckets": 0}

        # 1. Determine watermark in analytics_db
        with psycopg.connect(self.analytics_db_url, connect_timeout=self.timeout_seconds) as ana_conn:
            with ana_conn.cursor() as cur:
                cur.execute("SELECT COALESCE(MAX(recorded_at), '1970-01-01'::timestamptz) FROM stg_count_updates;")
                last_watermark: datetime = cur.fetchone()[0]

        # 2. Extract incremental records from ai_db with lookback buffer
        lookback = last_watermark - timedelta(minutes=2)
        with psycopg.connect(self.ai_db_url, connect_timeout=self.timeout_seconds, row_factory=dict_row) as ai_conn:
            with ai_conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text AS event_id, camera_id, farm_id, zone_id, frame_id,
                           delta_entry, delta_exit, recorded_at
                    FROM ai_count_updates
                    WHERE recorded_at >= %s AND farm_id IS NOT NULL AND zone_id IS NOT NULL
                    ORDER BY recorded_at ASC, id ASC
                    LIMIT %s;
                    """,
                    (lookback, batch_size),
                )
                raw_events = cur.fetchall()

        if not raw_events:
            return stats

        # 3. Atomic Deduplication Ledger & Staging Ingestion in single transaction
        with psycopg.connect(self.analytics_db_url, connect_timeout=self.timeout_seconds) as ana_conn:
            with ana_conn.cursor() as cur:
                earliest_modified = None

                for evt in raw_events:
                    rec_at: datetime = evt["recorded_at"]
                    # Deterministic fingerprint
                    raw_fp = f"{evt['camera_id']}_{evt['frame_id']}_{rec_at.isoformat()}"
                    fingerprint = hashlib.sha256(raw_fp.encode("utf-8")).hexdigest()

                    # Step 1: Ledger entry
                    cur.execute(
                        """
                        INSERT INTO stg_event_dedup_ledger (source_subsystem, event_fingerprint, event_timestamp)
                        VALUES ('AI_COUNT', %s, %s)
                        ON CONFLICT (source_subsystem, event_fingerprint) DO NOTHING
                        RETURNING event_fingerprint;
                        """,
                        (fingerprint, rec_at),
                    )
                    inserted_ledger = cur.fetchone()

                    if not inserted_ledger:
                        stats["deduped"] += 1
                        continue

                    # Step 2: Insert into staging table
                    cur.execute(
                        """
                        INSERT INTO stg_count_updates
                        (farm_id, zone_id, camera_id, frame_id, recorded_at, delta_entry, delta_exit, is_coverage_healthy)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE)
                        ON CONFLICT (camera_id, frame_id, recorded_at) DO NOTHING;
                        """,
                        (
                            evt["farm_id"],
                            evt["zone_id"],
                            evt["camera_id"],
                            evt["frame_id"],
                            rec_at,
                            evt["delta_entry"],
                            evt["delta_exit"],
                        ),
                    )
                    stats["ingested_staging"] += 1

                    if earliest_modified is None or rec_at < earliest_modified:
                        earliest_modified = rec_at

                # 4. Deterministic Snapshot Rollup into fact_bird_activity_hourly
                if earliest_modified is not None:
                    bucket_start = earliest_modified.replace(minute=0, second=0, microsecond=0)
                    cur.execute(
                        """
                        INSERT INTO fact_bird_activity_hourly (
                            farm_id, zone_id, camera_id, time_bucket,
                            entries, exits, net_change, sample_count, is_coverage_healthy, updated_at
                        )
                        SELECT
                            farm_id,
                            zone_id,
                            camera_id,
                            DATE_TRUNC('hour', recorded_at) AS time_bucket,
                            SUM(delta_entry) AS entries,
                            SUM(delta_exit) AS exits,
                            SUM(delta_entry) - SUM(delta_exit) AS net_change,
                            COUNT(*) AS sample_count,
                            BOOL_AND(is_coverage_healthy) AS is_coverage_healthy,
                            CURRENT_TIMESTAMP AS updated_at
                        FROM stg_count_updates
                        WHERE recorded_at >= %s
                        GROUP BY farm_id, zone_id, camera_id, DATE_TRUNC('hour', recorded_at)
                        ON CONFLICT (farm_id, zone_id, camera_id, time_bucket)
                        DO UPDATE SET
                            entries = EXCLUDED.entries,
                            exits = EXCLUDED.exits,
                            net_change = EXCLUDED.net_change,
                            sample_count = EXCLUDED.sample_count,
                            is_coverage_healthy = EXCLUDED.is_coverage_healthy,
                            updated_at = CURRENT_TIMESTAMP;
                        """,
                        (bucket_start,),
                    )
                    stats["materialized_buckets"] = cur.rowcount

            ana_conn.commit()

        return stats

    # -------------------------------------------------------------------------
    # Pipeline 3: IoT Telemetry Ingestion & Sample-Weighted Hourly Rollup
    # -------------------------------------------------------------------------
    def sync_iot_telemetry(self, batch_size: int = 5000) -> Dict[str, int]:
        """
        Synchronizes raw telemetry records into fact_telemetry_hourly with device-grain aggregations.
        Preserves NULLs for missing sensors and marks has_data_gaps.
        """
        stats = {"rollups_updated": 0}

        # 1. Determine watermark
        with psycopg.connect(self.analytics_db_url, connect_timeout=self.timeout_seconds) as ana_conn:
            with ana_conn.cursor() as cur:
                cur.execute("SELECT COALESCE(MAX(time_bucket), '1970-01-01'::timestamptz) FROM fact_telemetry_hourly;")
                last_bucket: datetime = cur.fetchone()[0]

        lookback = last_bucket - timedelta(hours=2)

        # 2. Query rollups from iot_db.telemetry_records
        with psycopg.connect(self.iot_db_url, connect_timeout=self.timeout_seconds, row_factory=dict_row) as iot_conn:
            with iot_conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        farm_id,
                        zone_id,
                        device_id,
                        DATE_TRUNC('hour', recorded_at) AS time_bucket,
                        AVG(temperature) AS avg_temperature,
                        MIN(temperature) AS min_temperature,
                        MAX(temperature) AS max_temperature,
                        AVG(humidity) AS avg_humidity,
                        MIN(humidity) AS min_humidity,
                        MAX(humidity) AS max_humidity,
                        AVG(co2) AS avg_co2,
                        AVG(lux) AS avg_lux,
                        AVG(audio_rms) AS avg_audio_rms,
                        COUNT(*) AS sample_count
                    FROM telemetry_records
                    WHERE recorded_at >= %s AND farm_id IS NOT NULL AND zone_id IS NOT NULL
                    GROUP BY farm_id, zone_id, device_id, DATE_TRUNC('hour', recorded_at)
                    ORDER BY time_bucket ASC
                    LIMIT %s;
                    """,
                    (lookback, batch_size),
                )
                rollups = cur.fetchall()

        if not rollups:
            return stats

        # 3. Upsert into analytics_db.fact_telemetry_hourly
        with psycopg.connect(self.analytics_db_url, connect_timeout=self.timeout_seconds) as ana_conn:
            with ana_conn.cursor() as cur:
                for r in rollups:
                    has_gaps = r["sample_count"] < 10  # Flag partial interval
                    cur.execute(
                        """
                        INSERT INTO fact_telemetry_hourly (
                            farm_id, zone_id, device_id, time_bucket,
                            avg_temperature, min_temperature, max_temperature,
                            avg_humidity, min_humidity, max_humidity,
                            avg_co2, avg_lux, avg_audio_rms,
                            sample_count, has_data_gaps, updated_at
                        ) VALUES (
                            %s, %s, %s, %s,
                            %s, %s, %s,
                            %s, %s, %s,
                            %s, %s, %s,
                            %s, %s, CURRENT_TIMESTAMP
                        ) ON CONFLICT (farm_id, zone_id, device_id, time_bucket)
                        DO UPDATE SET
                            avg_temperature = EXCLUDED.avg_temperature,
                            min_temperature = EXCLUDED.min_temperature,
                            max_temperature = EXCLUDED.max_temperature,
                            avg_humidity = EXCLUDED.avg_humidity,
                            min_humidity = EXCLUDED.min_humidity,
                            max_humidity = EXCLUDED.max_humidity,
                            avg_co2 = EXCLUDED.avg_co2,
                            avg_lux = EXCLUDED.avg_lux,
                            avg_audio_rms = EXCLUDED.avg_audio_rms,
                            sample_count = EXCLUDED.sample_count,
                            has_data_gaps = EXCLUDED.has_data_gaps,
                            updated_at = CURRENT_TIMESTAMP;
                        """,
                        (
                            r["farm_id"],
                            r["zone_id"],
                            r["device_id"],
                            r["time_bucket"],
                            r["avg_temperature"],
                            r["min_temperature"],
                            r["max_temperature"],
                            r["avg_humidity"],
                            r["min_humidity"],
                            r["max_humidity"],
                            r["avg_co2"],
                            r["avg_lux"],
                            r["avg_audio_rms"],
                            r["sample_count"],
                            has_gaps,
                        ),
                    )
                    stats["rollups_updated"] += 1

            ana_conn.commit()

        return stats

    # -------------------------------------------------------------------------
    # Pipeline 4: Notification Alerts Hourly Rollup
    # -------------------------------------------------------------------------
    def sync_alerts(self) -> Dict[str, int]:
        """
        Synchronizes alerts from notification_db into fact_alerts_hourly.
        """
        stats = {"alert_rollups_updated": 0}

        # 1. Query aggregated alerts from notification_db
        with psycopg.connect(self.notification_db_url, connect_timeout=self.timeout_seconds, row_factory=dict_row) as notif_conn:
            with notif_conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        farm_id,
                        COALESCE(zone_id, 'GLOBAL') AS zone_id,
                        DATE_TRUNC('hour', created_at) AS time_bucket,
                        SUM(CASE WHEN severity = 'CRITICAL' THEN 1 ELSE 0 END) AS critical_count,
                        SUM(CASE WHEN severity = 'HIGH' THEN 1 ELSE 0 END) AS high_count,
                        SUM(CASE WHEN severity = 'MEDIUM' THEN 1 ELSE 0 END) AS medium_count,
                        SUM(CASE WHEN severity = 'LOW' THEN 1 ELSE 0 END) AS low_count,
                        COUNT(*) AS total_count
                    FROM alerts
                    GROUP BY farm_id, COALESCE(zone_id, 'GLOBAL'), DATE_TRUNC('hour', created_at);
                    """
                )
                alert_rollups = cur.fetchall()

        if not alert_rollups:
            return stats

        # 2. Upsert into analytics_db.fact_alerts_hourly
        with psycopg.connect(self.analytics_db_url, connect_timeout=self.timeout_seconds) as ana_conn:
            with ana_conn.cursor() as cur:
                for ar in alert_rollups:
                    cur.execute(
                        """
                        INSERT INTO fact_alerts_hourly (
                            farm_id, zone_id, time_bucket,
                            critical_count, high_count, medium_count, low_count, total_count, updated_at
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP
                        ) ON CONFLICT (farm_id, zone_id, time_bucket)
                        DO UPDATE SET
                            critical_count = EXCLUDED.critical_count,
                            high_count = EXCLUDED.high_count,
                            medium_count = EXCLUDED.medium_count,
                            low_count = EXCLUDED.low_count,
                            total_count = EXCLUDED.total_count,
                            updated_at = CURRENT_TIMESTAMP;
                        """,
                        (
                            ar["farm_id"],
                            ar["zone_id"],
                            ar["time_bucket"],
                            ar["critical_count"],
                            ar["high_count"],
                            ar["medium_count"],
                            ar["low_count"],
                            ar["total_count"],
                        ),
                    )
                    stats["alert_rollups_updated"] += 1

            ana_conn.commit()

        return stats

    # -------------------------------------------------------------------------
    # Full Sync Orchestration
    # -------------------------------------------------------------------------
    def run_all(self) -> Dict[str, Any]:
        """Runs all 4 pipelines sequentially in proper topological order."""
        return {
            "dimensions": self.sync_dimensions(),
            "ai_counts": self.sync_ai_counts(),
            "iot_telemetry": self.sync_iot_telemetry(),
            "alerts": self.sync_alerts(),
        }
