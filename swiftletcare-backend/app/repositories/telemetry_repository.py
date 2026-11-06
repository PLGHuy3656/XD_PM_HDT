import logging
from datetime import datetime

from psycopg.types.json import Jsonb

from app.database import get_connection
from app.schemas.telemetry import TelemetryPayload

logger = logging.getLogger("telemetry.repository")


class TelemetryRepository:
    """
    Data-access layer for telemetry persistence and device state queries.
    Interacts with PostgreSQL/Supabase via psycopg v3.
    """

    def __init__(self, connection_factory=get_connection):
        self._get_connection = connection_factory

    def save_telemetry(
        self,
        house_code: str,
        payload: TelemetryPayload,
        recorded_at: datetime,
    ) -> None:
        """
        Validates device registration against house_code, inserts
        telemetry log, and upserts device_latest_state within a transaction.
        """
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                # 1. Device validation
                cur.execute(
                    """
                    SELECT d.id, z.zone_code
                    FROM public.devices d
                    JOIN public.houses h ON h.id = d.house_id
                    JOIN public.zones z ON z.id = d.zone_id
                    WHERE d.node_id = %s
                      AND h.house_code = %s
                      AND d.is_active = TRUE
                      AND z.house_id = h.id
                    """,
                    (payload.nodeId, house_code),
                )

                device = cur.fetchone()

                if device is None:
                    raise ValueError(
                        "Unknown, inactive, or mismatched device"
                    )

                device_id = device[0]
                metrics = payload.metrics.model_dump(by_alias=True)
                actuators = payload.actuators.model_dump()
                state = payload.state.model_dump()

                # 2. Telemetry INSERT
                cur.execute(
                    """
                    INSERT INTO public.telemetry (
                        device_id, recorded_at,
                        temperature, humidity, lux, co2,
                        audio_rms, audio_healthy,
                        actuators, device_state, raw_payload
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s
                    )
                    """,
                    (
                        device_id,
                        recorded_at,
                        metrics["temperature"],
                        metrics["humidity"],
                        metrics["lux"],
                        metrics["co2"],
                        metrics["audioRms"],
                        metrics["audioHealthy"],
                        Jsonb(actuators),
                        Jsonb(state),
                        Jsonb(payload.model_dump(by_alias=True)),
                    ),
                )

                # 3. Device latest state UPSERT
                cur.execute(
                    """
                    INSERT INTO public.device_latest_state (
                        device_id, recorded_at,
                        temperature, humidity, lux, co2,
                        audio_rms, audio_healthy,
                        actuators, device_state
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s
                    )
                    ON CONFLICT (device_id) DO UPDATE SET
                        recorded_at = EXCLUDED.recorded_at,
                        received_at = now(),
                        temperature = EXCLUDED.temperature,
                        humidity = EXCLUDED.humidity,
                        lux = EXCLUDED.lux,
                        co2 = EXCLUDED.co2,
                        audio_rms = EXCLUDED.audio_rms,
                        audio_healthy = EXCLUDED.audio_healthy,
                        actuators = EXCLUDED.actuators,
                        device_state = EXCLUDED.device_state
                    WHERE EXCLUDED.recorded_at
                          >= device_latest_state.recorded_at
                    """,
                    (
                        device_id,
                        recorded_at,
                        metrics["temperature"],
                        metrics["humidity"],
                        metrics["lux"],
                        metrics["co2"],
                        metrics["audioRms"],
                        metrics["audioHealthy"],
                        Jsonb(actuators),
                        Jsonb(state),
                    ),
                )


telemetry_repository = TelemetryRepository()
