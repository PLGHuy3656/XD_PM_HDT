"""
Legacy IoT Adapter

TODO(MICROSERVICE-BOUNDARY):
- Boundary Crossover: Reads runtime state (recorded_at, device_state JSONB) from legacy database.
- Future Service Owner: IoT Service (iot-service) owns device presence, MQTT ingestion, and runtime telemetry.
- Eventual Replacement: Replaced by IoT Service REST API calls (e.g., GET /api/iot/devices/state)
  or event-driven asynchronous projections via RabbitMQ.
- Isolation Principle: By isolating this temporary read in an adapter, Management domain
  repositories maintain strict database ownership over management_db with ZERO cross-database SQL joins.
"""

import logging
from typing import Any
import psycopg

from app.config import settings

logger = logging.getLogger(__name__)


class LegacyIoTAdapter:
    def __init__(self, db_url: str | None = None):
        self._db_url = db_url or settings.legacy_iot_database_url

    def _get_connection(self):
        if not self._db_url:
            return None
        try:
            return psycopg.connect(self._db_url, connect_timeout=5)
        except Exception as e:
            logger.warning(
                "Could not connect to legacy IoT database for runtime state: %s",
                e,
            )
            return None

    def get_devices_runtime_state(
        self, device_ids: list[str]
    ) -> dict[str, dict[str, Any]]:
        """
        Retrieves the latest runtime state for a list of device IDs from legacy device_latest_state.
        Returns a dict mapping device_id -> {"recorded_at": datetime, "device_state": dict}.
        """
        if not device_ids:
            return {}

        conn = self._get_connection()
        if not conn:
            return {}

        results = {}
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT device_id, recorded_at, device_state
                        FROM public.device_latest_state
                        WHERE device_id = ANY(%s);
                        """,
                        (device_ids,),
                    )
                    rows = cur.fetchall()
                    for row in rows:
                        results[str(row[0])] = {
                            "recorded_at": row[1],
                            "device_state": row[2] or {},
                        }
        except Exception as e:
            logger.warning("Error reading device runtime state from legacy IoT DB: %s", e)
        finally:
            conn.close()

        return results

    def get_devices_presence_counts(
        self, device_ids: list[str]
    ) -> tuple[int, int]:
        """
        Given a list of device IDs, returns (online_count, offline_count).
        A device is considered online if it has a record in device_latest_state.
        """
        if not device_ids:
            return 0, 0

        states = self.get_devices_runtime_state(device_ids)
        online_count = len(states)
        offline_count = max(0, len(device_ids) - online_count)
        return online_count, offline_count


legacy_iot_adapter = LegacyIoTAdapter()
