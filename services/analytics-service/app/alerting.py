import asyncio
import logging
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.authorization import get_analytics_device_contexts
from app.config import settings
from app.event_publisher import AnalyticsEventPublisher
from app.repository import (
    get_anomaly_baselines,
    get_latest_telemetry,
    get_pending_analytics_events,
    mark_analytics_event_failed,
    mark_analytics_event_published,
    open_analytics_alert,
    resolve_analytics_alert,
)

logger = logging.getLogger(__name__)
ANOMALY_METRICS = ("temperature", "humidity", "co2", "lux")
ANOMALY_MINIMUM_SAMPLES = 30
ANOMALY_MAD_MULTIPLIER = 3.0
ANOMALY_BASELINE_DAYS = 7
ANOMALY_BASELINE_DELAY = timedelta(minutes=5)


def _threshold_checks(row: tuple) -> dict[str, tuple[float, float, str]]:
    checks: dict[str, tuple[float, float, str]] = {}
    values = {
        "temperature": (row[2], row[6], row[7], "°C"),
        "humidity": (row[3], row[8], row[9], "%"),
    }

    for metric, (value, target, deadband, _unit) in values.items():
        if value is None or target is None or deadband is None:
            continue
        lower = float(target) - float(deadband)
        upper = float(target) + float(deadband)
        if value < lower:
            checks[metric] = (float(value), lower, "below")
        elif value > upper:
            checks[metric] = (float(value), upper, "above")

    co2, co2_threshold = row[4], row[10]
    if (
        co2 is not None
        and co2_threshold is not None
        and co2 > co2_threshold
    ):
        checks["co2"] = (float(co2), float(co2_threshold), "above")

    return checks


def _anomaly_check(
    metric: str,
    value: float | None,
    baseline: tuple[int, float | None, float | None] | None,
) -> tuple[float, float, str, dict] | None:
    if value is None or baseline is None:
        return None

    sample_count, median, mad = baseline
    if (
        sample_count < ANOMALY_MINIMUM_SAMPLES
        or median is None
        or mad is None
    ):
        return None

    distance = abs(value - median)
    if mad == 0:
        is_anomaly = distance > 0
        threshold = median
    else:
        threshold = median + (
            ANOMALY_MAD_MULTIPLIER * mad
            * (1 if value >= median else -1)
        )
        is_anomaly = distance > ANOMALY_MAD_MULTIPLIER * mad

    if not is_anomaly:
        return None

    direction = "above" if value > median else "below"
    return (
        value,
        threshold,
        direction,
        {
            "method": "rolling_median_mad",
            "median": median,
            "mad": mad,
            "sample_count": sample_count,
            "threshold": threshold,
        },
    )


def run_monitoring_cycle() -> None:
    contexts = get_analytics_device_contexts()
    context_by_node = {item["node_id"]: item for item in contexts}
    node_ids = list(context_by_node)
    latest_rows = get_latest_telemetry(node_ids)

    now = datetime.now(timezone.utc)
    baseline_start = now - timedelta(days=ANOMALY_BASELINE_DAYS)
    baseline_end = now - ANOMALY_BASELINE_DELAY
    baselines = get_anomaly_baselines(
        node_ids,
        baseline_start,
        baseline_end,
    )

    for row in latest_rows:
        node_id = row[0]
        context = context_by_node.get(node_id)
        if context is None:
            continue

        threshold_checks = _threshold_checks(row)
        for metric in ("temperature", "humidity", "co2"):
            alert_key = f"{node_id}:threshold_exceeded:{metric}"
            check = threshold_checks.get(metric)
            if check is None:
                resolve_analytics_alert(alert_key)
                continue

            value, threshold, direction = check
            _record_alert(
                context=context,
                node_id=node_id,
                alert_key=alert_key,
                alert_type="threshold_exceeded",
                metric=metric,
                value=value,
                threshold=threshold,
                direction=direction,
                baseline={},
            )

        metric_values = {
            "temperature": row[2],
            "humidity": row[3],
            "co2": row[4],
            "lux": row[5],
        }
        for metric in ANOMALY_METRICS:
            alert_key = f"{node_id}:anomaly_detected:{metric}"
            value = metric_values[metric]
            check = _anomaly_check(
                metric,
                float(value) if value is not None else None,
                baselines.get((node_id, metric)),
            )
            if check is None:
                if baselines.get((node_id, metric), (0, None, None))[0] >= ANOMALY_MINIMUM_SAMPLES:
                    resolve_analytics_alert(alert_key)
                continue

            anomaly_value, threshold, direction, baseline = check
            _record_alert(
                context=context,
                node_id=node_id,
                alert_key=alert_key,
                alert_type="anomaly_detected",
                metric=metric,
                value=anomaly_value,
                threshold=threshold,
                direction=direction,
                baseline=baseline,
            )


def _record_alert(
    *,
    context: dict,
    node_id: str,
    alert_key: str,
    alert_type: str,
    metric: str,
    value: float,
    threshold: float | None,
    direction: str,
    baseline: dict,
) -> None:
    if not context["recipient_user_ids"]:
        logger.warning(
            "Alert for node %s was not published because its farm has no "
            "owner or assigned technician",
            node_id,
        )
        recipients = []
    else:
        recipients = context["recipient_user_ids"]

    event_type = (
        "environment.threshold_exceeded"
        if alert_type == "threshold_exceeded"
        else "environment.anomaly_detected"
    )
    units = {
        "temperature": "°C",
        "humidity": "%",
        "co2": "ppm",
        "lux": "lux",
    }
    event_id = str(uuid4())
    occurred_at = datetime.now(timezone.utc).isoformat()
    # Canonical Domain Event Envelope V1 (compatible with Notification Service PR #30)
    event = {
        "eventId": event_id,
        "eventType": event_type,
        "eventVersion": "1.0",
        "occurredAt": occurred_at,
        "producer": "analytics-service",
        "correlationId": event_id,
        "payload": {
            "recipientUserIds": recipients,
            "nodeId": node_id,
            "node_id": node_id,
            "farmId": context["farm_id"],
            "farm_id": context["farm_id"],
            "farm_code": context.get("farm_code"),
            "farm_name": context["farm_name"],
            "zone_name": context.get("zone_name"),
            "metric": metric,
            "value": value,
            "unit": units[metric],
            "threshold": threshold,
            "direction": direction,
            "baseline": baseline,
        },
    }
    open_analytics_alert(
        alert_key=alert_key,
        node_id=node_id,
        farm_id=context["farm_id"],
        farm_name=context["farm_name"],
        zone_name=context.get("zone_name"),
        alert_type=alert_type,
        metric=metric,
        value=value,
        threshold=threshold,
        direction=direction,
        baseline=baseline,
        event=event,
    )


async def _publish_outbox(
    publisher: AnalyticsEventPublisher | None,
) -> None:
    if publisher is None:
        return

    for event_id, payload in await asyncio.to_thread(
        get_pending_analytics_events,
    ):
        try:
            event_type = payload.get("eventType") or payload["event_type"]
            await publisher.publish(event_type, payload)
        except Exception as exc:
            await asyncio.to_thread(
                mark_analytics_event_failed,
                event_id,
                str(exc),
            )
            logger.exception(
                "Failed to publish analytics event %s",
                event_id,
            )
        else:
            await asyncio.to_thread(
                mark_analytics_event_published,
                event_id,
            )


async def run_analytics_monitor(
    rabbitmq_url: str,
    exchange_name: str,
) -> None:
    publisher = (
        AnalyticsEventPublisher(rabbitmq_url, exchange_name)
        if rabbitmq_url
        else None
    )
    if publisher is None:
        logger.warning(
            "RabbitMQ is not configured; analytics alerts will be stored "
            "but not delivered"
        )

    try:
        while True:
            try:
                await asyncio.to_thread(run_monitoring_cycle)
                await _publish_outbox(publisher)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Analytics monitoring cycle failed")
            await asyncio.sleep(max(5, settings.monitor_interval_seconds))
    finally:
        if publisher is not None:
            await publisher.close()
