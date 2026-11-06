"""Offline unit tests for SwiftletCare RabbitMQ topology & declarative contracts (CP7.1).

Validates topology definition, exchange attributes, queue dead-letter routing,
binding patterns, and canonical envelope schema without requiring a running broker.
"""
from __future__ import annotations

import base64
import json
import pytest

from infrastructure.rabbitmq.constants import (
    DEFAULT_PREFETCH,
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
from infrastructure.rabbitmq.topology import (
    BindingDefinition,
    ExchangeDefinition,
    QueueDefinition,
    get_v1_topology,
)
from infrastructure.rabbitmq.verifier import create_test_envelope


def test_topology_definition_completeness():
    """Verify that get_v1_topology creates all required exchanges, queues, and bindings."""
    topology = get_v1_topology(retry_ttl_ms=3000)
    assert isinstance(topology, dict)
    assert len(topology["exchanges"]) == 4
    assert len(topology["queues"]) == 3
    assert len(topology["bindings"]) == 8


def test_exchanges_attributes():
    """Verify exchanges types, durability, and naming conventions."""
    topology = get_v1_topology()
    exchanges_by_name = {ex.name: ex for ex in topology["exchanges"]}

    # 1. Topic Domain Events exchange
    assert EXCHANGE_DOMAIN_EVENTS in exchanges_by_name
    domain_ex = exchanges_by_name[EXCHANGE_DOMAIN_EVENTS]
    assert domain_ex.type == "topic"
    assert domain_ex.durable is True
    assert domain_ex.auto_delete is False

    # 2. Retry exchange
    assert EXCHANGE_NOTIFICATION_RETRY in exchanges_by_name
    retry_ex = exchanges_by_name[EXCHANGE_NOTIFICATION_RETRY]
    assert retry_ex.type == "direct"
    assert retry_ex.durable is True

    # 3. Retry Return exchange
    assert EXCHANGE_NOTIFICATION_RETRY_RETURN in exchanges_by_name
    retry_ret_ex = exchanges_by_name[EXCHANGE_NOTIFICATION_RETRY_RETURN]
    assert retry_ret_ex.type == "direct"
    assert retry_ret_ex.durable is True

    # 4. DLX exchange
    assert EXCHANGE_NOTIFICATION_DLX in exchanges_by_name
    dlx_ex = exchanges_by_name[EXCHANGE_NOTIFICATION_DLX]
    assert dlx_ex.type == "direct"
    assert dlx_ex.durable is True


def test_queues_dead_letter_and_ttl_arguments():
    """Verify dead-letter exchange, routing keys, and TTL arguments on queues."""
    custom_ttl = 8000
    topology = get_v1_topology(retry_ttl_ms=custom_ttl)
    queues_by_name = {q.name: q for q in topology["queues"]}

    # 1. Main Queue (Notification)
    assert QUEUE_NOTIFICATION_MAIN in queues_by_name
    main_q = queues_by_name[QUEUE_NOTIFICATION_MAIN]
    assert main_q.durable is True
    assert main_q.auto_delete is False
    assert main_q.arguments.get("x-dead-letter-exchange") == EXCHANGE_NOTIFICATION_DLX
    assert main_q.arguments.get("x-dead-letter-routing-key") == ROUTING_KEY_DLQ

    # 2. Retry Queue (Dead-letter back to Main queue upon expiration)
    assert QUEUE_NOTIFICATION_RETRY in queues_by_name
    retry_q = queues_by_name[QUEUE_NOTIFICATION_RETRY]
    assert retry_q.durable is True
    assert retry_q.arguments.get("x-message-ttl") == custom_ttl
    assert retry_q.arguments.get("x-dead-letter-exchange") == EXCHANGE_NOTIFICATION_RETRY_RETURN
    assert retry_q.arguments.get("x-dead-letter-routing-key") == ROUTING_KEY_RETRY_RETURN

    # 3. Dead Letter Queue (DLQ)
    assert QUEUE_NOTIFICATION_DLQ in queues_by_name
    dlq_q = queues_by_name[QUEUE_NOTIFICATION_DLQ]
    assert dlq_q.durable is True
    assert dlq_q.arguments == {}


def test_binding_patterns_and_isolation():
    """Verify topic bindings and ensure excluded high-frequency patterns are omitted."""
    topology = get_v1_topology()

    # Collect all binding keys on the main notification queue
    main_bindings = [
        b.routing_key
        for b in topology["bindings"]
        if b.destination_queue == QUEUE_NOTIFICATION_MAIN and b.source_exchange == EXCHANGE_DOMAIN_EVENTS
    ]

    # Verify all canonical patterns are registered
    for pattern in NOTIFICATION_BINDING_PATTERNS:
        assert pattern in main_bindings, f"Missing expected binding: {pattern}"

    # Verify forbidden patterns are strictly EXCLUDED
    for forbidden in EXCLUDED_PATTERNS:
        assert forbidden not in main_bindings, f"Forbidden telemetry pattern bound to main queue: {forbidden}"

    # Verify retry and DLQ bindings
    bindings_by_dest = {b.destination_queue: b for b in topology["bindings"]}
    assert bindings_by_dest[QUEUE_NOTIFICATION_RETRY].source_exchange == EXCHANGE_NOTIFICATION_RETRY
    assert bindings_by_dest[QUEUE_NOTIFICATION_RETRY].routing_key == ROUTING_KEY_RETRY_QUEUE

    assert bindings_by_dest[QUEUE_NOTIFICATION_DLQ].source_exchange == EXCHANGE_NOTIFICATION_DLX
    assert bindings_by_dest[QUEUE_NOTIFICATION_DLQ].routing_key == ROUTING_KEY_DLQ


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
