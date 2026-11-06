"""Offline unit tests for SwiftletCare RabbitMQ topology & declarative contracts (CP7.1).

Validates topology definition, exchange attributes, queue dead-letter routing,
binding patterns, and canonical envelope schema without requiring a running broker.
"""
from __future__ import annotations

import base64

from infrastructure.rabbitmq.constants import (
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
    EXCHANGE_NOTIFICATION_RETRY_RETURN,
    EXCLUDED_PATTERNS,
    NOTIFICATION_BINDING_PATTERNS,
    QUEUE_NOTIFICATION_DLQ,
    QUEUE_NOTIFICATION_MAIN,
    QUEUE_NOTIFICATION_RETRY,
    ROUTING_KEY_DLQ,
    ROUTING_KEY_RETRY_QUEUE,
    ROUTING_KEY_RETRY_RETURN,
)
from infrastructure.rabbitmq.declarator import RabbitMQDeclarator
from infrastructure.rabbitmq.topology import get_v1_topology
from infrastructure.rabbitmq.verifier import create_test_envelope


def test_topology_definition_completeness():
    """Verify that get_v1_topology creates all required exchanges, queues, and bindings."""
    topology = get_v1_topology(retry_ttl_ms=3000)
    assert isinstance(topology, dict)
    assert len(topology["exchanges"]) == 4
    assert len(topology["queues"]) == 3
    assert len(topology["bindings"]) == 8


def test_exchanges_attributes():
    """Verify exchange literal names, types, durability, and naming conventions."""
    # Literal name assertions (Frozen CP7.0 contract)
    assert EXCHANGE_DOMAIN_EVENTS == "swiftlet.domain.events"
    assert EXCHANGE_NOTIFICATION_RETRY == "swiftlet.notification.retry"
    assert EXCHANGE_NOTIFICATION_RETRY_RETURN == "swiftlet.notification.retry-return"
    assert EXCHANGE_NOTIFICATION_DLX == "swiftlet.notification.dlx"

    topology = get_v1_topology()
    exchanges_by_name = {ex.name: ex for ex in topology["exchanges"]}

    # 1. Topic Domain Events exchange
    assert "swiftlet.domain.events" in exchanges_by_name
    domain_ex = exchanges_by_name["swiftlet.domain.events"]
    assert domain_ex.type == "topic"
    assert domain_ex.durable is True
    assert domain_ex.auto_delete is False

    # 2. Retry exchange
    assert "swiftlet.notification.retry" in exchanges_by_name
    retry_ex = exchanges_by_name["swiftlet.notification.retry"]
    assert retry_ex.type == "direct"
    assert retry_ex.durable is True

    # 3. Retry Return exchange
    assert "swiftlet.notification.retry-return" in exchanges_by_name
    retry_ret_ex = exchanges_by_name["swiftlet.notification.retry-return"]
    assert retry_ret_ex.type == "direct"
    assert retry_ret_ex.durable is True

    # 4. DLX exchange
    assert "swiftlet.notification.dlx" in exchanges_by_name
    dlx_ex = exchanges_by_name["swiftlet.notification.dlx"]
    assert dlx_ex.type == "direct"
    assert dlx_ex.durable is True


def test_queues_dead_letter_and_ttl_arguments():
    """Verify queue literal names, dead-letter routing, and TTL arguments."""
    # Literal queue and routing key assertions
    assert QUEUE_NOTIFICATION_MAIN == "notification.alert-events.v1"
    assert QUEUE_NOTIFICATION_RETRY == "notification.alert-events.v1.retry"
    assert QUEUE_NOTIFICATION_DLQ == "notification.alert-events.v1.dlq"
    assert ROUTING_KEY_DLQ == "notification.alert-events.v1.dlq"
    assert ROUTING_KEY_RETRY_QUEUE == "notification.alert-events.v1.retry"
    assert ROUTING_KEY_RETRY_RETURN == "notification.alert-events.v1.retry-return"

    custom_ttl = 8000
    topology = get_v1_topology(retry_ttl_ms=custom_ttl)
    queues_by_name = {q.name: q for q in topology["queues"]}

    # 1. Main Queue (Notification)
    assert "notification.alert-events.v1" in queues_by_name
    main_q = queues_by_name["notification.alert-events.v1"]
    assert main_q.durable is True
    assert main_q.auto_delete is False
    assert main_q.arguments.get("x-dead-letter-exchange") == "swiftlet.notification.dlx"
    assert main_q.arguments.get("x-dead-letter-routing-key") == "notification.alert-events.v1.dlq"

    # 2. Retry Queue (Dead-letter back to Main queue upon expiration)
    assert "notification.alert-events.v1.retry" in queues_by_name
    retry_q = queues_by_name["notification.alert-events.v1.retry"]
    assert retry_q.durable is True
    assert retry_q.arguments.get("x-message-ttl") == custom_ttl
    assert retry_q.arguments.get("x-dead-letter-exchange") == "swiftlet.notification.retry-return"
    assert retry_q.arguments.get("x-dead-letter-routing-key") == "notification.alert-events.v1.retry-return"

    # 3. Dead Letter Queue (DLQ)
    assert "notification.alert-events.v1.dlq" in queues_by_name
    dlq_q = queues_by_name["notification.alert-events.v1.dlq"]
    assert dlq_q.durable is True
    assert dlq_q.arguments == {}


def test_binding_patterns_and_isolation():
    """Verify topic bindings, retry-return routing, and exclusion of raw telemetry."""
    topology = get_v1_topology()

    # 1. Main notification queue bindings from domain events exchange
    main_domain_bindings = [
        b.routing_key
        for b in topology["bindings"]
        if b.destination_queue == "notification.alert-events.v1"
        and b.source_exchange == "swiftlet.domain.events"
    ]
    for pattern in NOTIFICATION_BINDING_PATTERNS:
        assert pattern in main_domain_bindings, f"Missing expected binding: {pattern}"

    for forbidden in EXCLUDED_PATTERNS:
        assert forbidden not in main_domain_bindings, f"Forbidden telemetry pattern bound to main queue: {forbidden}"

    # 2. Retry queue binding from retry exchange
    retry_bindings = [
        b
        for b in topology["bindings"]
        if b.destination_queue == "notification.alert-events.v1.retry"
        and b.source_exchange == "swiftlet.notification.retry"
    ]
    assert len(retry_bindings) == 1
    assert retry_bindings[0].routing_key == "notification.alert-events.v1.retry"

    # 3. Explicit assertion for binding: swiftlet.notification.retry-return -> notification.alert-events.v1
    retry_return_bindings = [
        b
        for b in topology["bindings"]
        if b.destination_queue == "notification.alert-events.v1"
        and b.source_exchange == "swiftlet.notification.retry-return"
    ]
    assert len(retry_return_bindings) == 1
    assert retry_return_bindings[0].routing_key == "notification.alert-events.v1.retry-return"

    # 4. DLQ binding from dlx exchange
    dlq_bindings = [
        b
        for b in topology["bindings"]
        if b.destination_queue == "notification.alert-events.v1.dlq"
        and b.source_exchange == "swiftlet.notification.dlx"
    ]
    assert len(dlq_bindings) == 1
    assert dlq_bindings[0].routing_key == "notification.alert-events.v1.dlq"


def test_declarator_offline_helpers():
    """Verify vhost URL encoding and HTTP basic auth header formatting."""
    declarator = RabbitMQDeclarator(
        base_url="http://127.0.0.1:15672",
        username="testuser",
        password="testpassword",
        vhost="/",
    )
    assert declarator.encoded_vhost == "%2F"

    custom_vhost_declarator = RabbitMQDeclarator(vhost="swiftlet_vhost")
    assert custom_vhost_declarator.encoded_vhost == "swiftlet_vhost"

    expected_auth = "Basic " + base64.b64encode(b"testuser:testpassword").decode()
    assert declarator._auth_header == expected_auth


def test_canonical_envelope_structure():
    """Verify test envelope schema adheres to the frozen CP7.0 contract."""
    payload = {"temperature": 39.5, "device_id": "swc-node-01"}
    envelope = create_test_envelope(
        event_type="iot.environment.high_temperature.started",
        payload=payload,
        producer="test-runner",
    )

    required_keys = {
        ENVELOPE_FIELD_EVENT_ID,
        ENVELOPE_FIELD_EVENT_TYPE,
        ENVELOPE_FIELD_EVENT_VERSION,
        ENVELOPE_FIELD_OCCURRED_AT,
        ENVELOPE_FIELD_PRODUCER,
        ENVELOPE_FIELD_CORRELATION_ID,
        ENVELOPE_FIELD_PAYLOAD,
    }
    assert required_keys.issubset(set(envelope.keys()))
    assert envelope[ENVELOPE_FIELD_EVENT_VERSION] == "1.0"
    assert envelope[ENVELOPE_FIELD_EVENT_TYPE] == "iot.environment.high_temperature.started"
    assert envelope[ENVELOPE_FIELD_PAYLOAD] == payload
    assert envelope[ENVELOPE_FIELD_PRODUCER] == "test-runner"
