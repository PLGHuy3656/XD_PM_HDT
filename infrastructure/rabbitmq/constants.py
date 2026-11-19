"""Constants and canonical terminology for RabbitMQ infrastructure (CP7.1)."""
from __future__ import annotations

# Exchanges
EXCHANGE_DOMAIN_EVENTS = "swiftlet.domain.events"
EXCHANGE_NOTIFICATION_RETRY = "swiftlet.notification.retry"
EXCHANGE_NOTIFICATION_RETRY_RETURN = "swiftlet.notification.retry-return"
EXCHANGE_NOTIFICATION_DLX = "swiftlet.notification.dlx"

# Queues
QUEUE_NOTIFICATION_MAIN = "notification.alert-events.v1"
QUEUE_NOTIFICATION_RETRY = "notification.alert-events.v1.retry"
QUEUE_NOTIFICATION_DLQ = "notification.alert-events.v1.dlq"

# Dedicated Routing Keys for Retry & DLQ
ROUTING_KEY_RETRY_QUEUE = "notification.alert-events.v1.retry"
ROUTING_KEY_RETRY_RETURN = "notification.alert-events.v1.retry-return"
ROUTING_KEY_DLQ = "notification.alert-events.v1.dlq"

# Canonical Notification Bindings (Frozen CP7.0)
NOTIFICATION_BINDING_PATTERNS = [
    "iot.environment.#",
    "iot.audio.#",
    "iot.device.#",
    "iot.command.failed",
    "ai.predator.detected",
]

# Explicitly Forbidden Bindings on Notification Main Queue
EXCLUDED_PATTERNS = [
    "iot.telemetry.#",
    "ai.count.#",
    "ai.entry.#",
    "ai.exit.#",
]

# Envelope Terminology (Frozen CP7.0)
ENVELOPE_FIELD_EVENT_ID = "eventId"
ENVELOPE_FIELD_EVENT_TYPE = "eventType"
ENVELOPE_FIELD_EVENT_VERSION = "eventVersion"
ENVELOPE_FIELD_OCCURRED_AT = "occurredAt"
ENVELOPE_FIELD_PRODUCER = "producer"
ENVELOPE_FIELD_CORRELATION_ID = "correlationId"
ENVELOPE_FIELD_PAYLOAD = "payload"

# Defaults
DEFAULT_RETRY_TTL_MS = 5000  # 5 seconds for local development/testing
DEFAULT_PREFETCH = 10
