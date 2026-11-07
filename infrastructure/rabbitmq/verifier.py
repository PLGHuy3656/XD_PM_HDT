"""Automated verification suite for RabbitMQ topology, routing, and retry/DLQ (CP7.1)."""
from __future__ import annotations

import json
import time
import uuid
from typing import Any, Dict, List, Optional

from infrastructure.rabbitmq.constants import (
    DEFAULT_RETRY_TTL_MS,
    ENVELOPE_FIELD_CORRELATION_ID,
    ENVELOPE_FIELD_EVENT_ID,
    ENVELOPE_FIELD_EVENT_TYPE,
    ENVELOPE_FIELD_EVENT_VERSION,
    ENVELOPE_FIELD_OCCURRED_AT,
    ENVELOPE_FIELD_PAYLOAD,
    ENVELOPE_FIELD_PRODUCER,
    EXCHANGE_DOMAIN_EVENTS,
    EXCHANGE_NOTIFICATION_DLX,
    EXCHANGE_NOTIFICATION_RETRY,
    QUEUE_NOTIFICATION_DLQ,
    QUEUE_NOTIFICATION_MAIN,
    QUEUE_NOTIFICATION_RETRY,
    ROUTING_KEY_DLQ,
    ROUTING_KEY_RETRY_QUEUE,
)
from infrastructure.rabbitmq.declarator import RabbitMQDeclarator


def create_test_envelope(
    event_type: str,
    payload: Dict[str, Any],
    producer: str = "test-harness",
) -> Dict[str, Any]:
    return {
        ENVELOPE_FIELD_EVENT_ID: f"evt_{uuid.uuid4().hex[:12]}",
        ENVELOPE_FIELD_EVENT_TYPE: event_type,
        ENVELOPE_FIELD_EVENT_VERSION: "1.0",
        ENVELOPE_FIELD_OCCURRED_AT: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        ENVELOPE_FIELD_PRODUCER: producer,
        ENVELOPE_FIELD_CORRELATION_ID: f"corr_{uuid.uuid4().hex[:8]}",
        ENVELOPE_FIELD_PAYLOAD: payload,
    }


def drain_queue(declarator: RabbitMQDeclarator, queue_name: str) -> int:
    """Drain and discard any existing messages from a queue."""
    msgs = declarator.get_messages(queue_name, count=100, ackmode="ack_requeue_false")
    return len(msgs)


def run_topology_verification(declarator: Optional[RabbitMQDeclarator] = None) -> Dict[str, Any]:
    d = declarator or RabbitMQDeclarator()

    print("=" * 80)
    print("CP7.1 RABBITMQ TOPOLOGY & INFRASTRUCTURE VERIFICATION")
    print("=" * 80)

    # 1. Apply Topology
    print("\n[Step 1] Applying V1 RabbitMQ Topology...")
    counts = d.apply_topology(retry_ttl_ms=DEFAULT_RETRY_TTL_MS)
    print(f"  Topology declared: {counts['exchanges']} exchanges, {counts['queues']} queues, {counts['bindings']} bindings.")

    # 2. Drain test queues before testing
    print("\n[Step 2] Draining test queues...")
    for q in [QUEUE_NOTIFICATION_MAIN, QUEUE_NOTIFICATION_RETRY, QUEUE_NOTIFICATION_DLQ]:
        drain_queue(d, q)
    print("  All queues drained clean.")

    results: Dict[str, Any] = {
        "positive_routing": {},
        "negative_routing": {},
        "retry_return": {},
        "dlq": {},
        "x_death_inspection": {},
    }

    # 3. Main & Wildcard Positive Routing Tests
    print("\n[Step 3] Positive Routing Tests (Must enter notification.alert-events.v1):")
    positive_keys = [
        "iot.environment.high_temperature.started",
        "iot.environment.high_temperature.recovered",
        "iot.device.offline",
        "iot.device.online",
        "iot.audio.fault.started",
        "iot.command.failed",
        "ai.predator.detected",
    ]

    for key in positive_keys:
        drain_queue(d, QUEUE_NOTIFICATION_MAIN)
        envelope = create_test_envelope(key, {"test": True, "target": key})
        routed = d.publish_message(EXCHANGE_DOMAIN_EVENTS, key, envelope)
        
        # Verify message arrived in main queue
        msgs = d.get_messages(QUEUE_NOTIFICATION_MAIN, count=1, ackmode="ack_requeue_false")
        passed = routed and len(msgs) == 1
        if passed:
            payload_data = json.loads(msgs[0]["payload"])
            assert payload_data[ENVELOPE_FIELD_EVENT_ID] == envelope[ENVELOPE_FIELD_EVENT_ID]
            assert msgs[0]["routing_key"] == key
            assert msgs[0]["exchange"] == EXCHANGE_DOMAIN_EVENTS

        results["positive_routing"][key] = {
            "routed": routed,
            "received_count": len(msgs),
            "passed": passed,
        }
        print(f"  - [{('PASS' if passed else 'FAIL')}] key='{key}' -> routed={routed}, received={len(msgs)}")
        assert passed, f"Positive routing failed for key '{key}'"

    # Drain main queue before negative tests
    drain_queue(d, QUEUE_NOTIFICATION_MAIN)

    # 4. Negative Routing Tests (Must NOT enter notification.alert-events.v1)
    print("\n[Step 4] Negative Routing Tests (Must NOT enter notification.alert-events.v1):")
    negative_keys = [
        "iot.telemetry.raw",
        "ai.count.updated",
        "ai.entry.detected",
        "ai.exit.detected",
        "management.user.updated",
    ]

    for key in negative_keys:
        drain_queue(d, QUEUE_NOTIFICATION_MAIN)
        envelope = create_test_envelope(key, {"telemetry": 123.45})
        d.publish_message(EXCHANGE_DOMAIN_EVENTS, key, envelope)
        
        # Query main queue to verify zero messages arrived
        msgs = d.get_messages(QUEUE_NOTIFICATION_MAIN, count=1, ackmode="ack_requeue_false")
        passed = len(msgs) == 0
        results["negative_routing"][key] = {
            "received_count": len(msgs),
            "passed": passed,
        }
        print(f"  - [{('PASS' if passed else 'FAIL')}] key='{key}' -> received={len(msgs)} (0 expected)")
        assert passed, f"Negative routing failed for key '{key}', message entered main queue!"

    # 5. Retry-Return Test
    print("\n[Step 5] Retry-Return Topology Test:")
    print(f"  Injecting message into '{EXCHANGE_NOTIFICATION_RETRY}' with routing_key='{ROUTING_KEY_RETRY_QUEUE}'...")
    drain_queue(d, QUEUE_NOTIFICATION_MAIN)
    drain_queue(d, QUEUE_NOTIFICATION_RETRY)

    retry_envelope = create_test_envelope(
        "iot.environment.high_temperature.started",
        {"simulation": "transient_failure"},
    )
    d.publish_message(
        exchange=EXCHANGE_NOTIFICATION_RETRY,
        routing_key=ROUTING_KEY_RETRY_QUEUE,
        payload=retry_envelope,
    )

    # Inspect retry queue (without consuming - ackmode=ack_requeue_true)
    retry_msgs = d.get_messages(QUEUE_NOTIFICATION_RETRY, count=1, ackmode="ack_requeue_true")
    print(f"  Message entered retry queue '{QUEUE_NOTIFICATION_RETRY}': count={len(retry_msgs)}")
    assert len(retry_msgs) == 1, "Retry queue did not receive message!"

    ttl_seconds = DEFAULT_RETRY_TTL_MS / 1000
    print(f"  Waiting for TTL ({ttl_seconds}s) to expire...")
    time.sleep(ttl_seconds + 0.8)

    # Verify retry queue is now empty
    retry_msgs_after = d.get_messages(QUEUE_NOTIFICATION_RETRY, count=1, ackmode="ack_requeue_false")
    print(f"  After TTL expiration:")
    print(f"    - Retry queue messages : {len(retry_msgs_after)} (0 expected, expired)")
    assert len(retry_msgs_after) == 0, "Message remained in retry queue after TTL expired!"

    # Verify main queue has received the message back via swiftlet.notification.retry-return!
    main_msgs_after = d.get_messages(QUEUE_NOTIFICATION_MAIN, count=1, ackmode="ack_requeue_false")
    print(f"    - Main queue messages  : {len(main_msgs_after)} (1 expected - routed back via retry-return!)")
    assert len(main_msgs_after) == 1, "Message was not returned to main queue after TTL expiration!"

    returned_msg = main_msgs_after[0]
    returned_payload = json.loads(returned_msg["payload"])
    assert returned_payload[ENVELOPE_FIELD_EVENT_ID] == retry_envelope[ENVELOPE_FIELD_EVENT_ID]
    results["retry_return"]["passed"] = True

    # 6. Inspect x-death metadata in returned message
    print("\n[Step 6] Inspecting Returned Message Headers & x-death Metadata:")
    headers = returned_msg.get("properties", {}).get("headers", {})
    x_death = headers.get("x-death", [])
    print(f"  x-death entries count: {len(x_death)}")
    assert len(x_death) >= 1, "Expected x-death header in dead-lettered message!"
    first_death = x_death[0]
    print(f"    - Dead queue  : {first_death.get('queue')}")
    print(f"    - Reason      : {first_death.get('reason')}")
    print(f"    - Count       : {first_death.get('count')}")
    print(f"    - Exchange    : {first_death.get('exchange')}")
    print(f"    - Routing key : {first_death.get('routing-keys')}")

    assert first_death.get("queue") == QUEUE_NOTIFICATION_RETRY
    assert first_death.get("reason") == "expired"
    results["x_death_inspection"] = first_death

    # 7. DLQ Test
    print("\n[Step 7] Dead Letter Queue (DLQ) Test:")
    drain_queue(d, QUEUE_NOTIFICATION_DLQ)
    dlq_envelope = create_test_envelope(
        "iot.environment.high_temperature.started",
        {"error": "max_retries_exhausted"},
    )
    d.publish_message(
        exchange=EXCHANGE_NOTIFICATION_DLX,
        routing_key=ROUTING_KEY_DLQ,
        payload=dlq_envelope,
    )
    dlq_msgs = d.get_messages(QUEUE_NOTIFICATION_DLQ, count=1, ackmode="ack_requeue_false")
    print(f"  Message routed to DLQ '{QUEUE_NOTIFICATION_DLQ}': count={len(dlq_msgs)}")
    assert len(dlq_msgs) == 1, "DLQ did not receive permanently failed message!"
    results["dlq"]["passed"] = True

    print("\n" + "=" * 80)
    print("ALL RABBITMQ TOPOLOGY TESTS PASSED WITH 100% CANONICAL COMPLIANCE!")
    print("=" * 80)
    return results


if __name__ == "__main__":
    run_topology_verification()
