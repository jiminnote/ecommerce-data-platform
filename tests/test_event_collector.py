"""Tests for the Event Collector module."""

from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from src.event_collector.app import app
from src.event_collector.models import (
    DeviceType,
    EventBatch,
    EventType,
    ProductViewEvent,
    PurchaseEvent,
    SearchEvent,
    UserEvent,
)


class TestUserEventModel:
    """Test UserEvent Pydantic model validation."""

    def test_valid_event(self):
        event = UserEvent(
            event_id=str(uuid.uuid4()),
            event_type=EventType.PAGE_VIEW,
            session_id="sess-123",
            device_type=DeviceType.IOS,
            user_id=42,
        )
        assert event.event_type == EventType.PAGE_VIEW
        assert event.user_id == 42

    def test_event_to_bigquery_row(self):
        event = UserEvent(
            event_id="test-event-12345",
            event_type=EventType.PRODUCT_VIEW,
            session_id="sess-abc",
            device_type=DeviceType.WEB_DESKTOP,
            user_id=100,
            page_url="/products/123",
        )
        row = event.to_bigquery_row()

        assert row["event_id"] == "test-event-12345"
        assert row["event_type"] == "product_view"
        assert row["user_id"] == 100
        assert row["page_url"] == "/products/123"
        assert "ingested_at" in row

    def test_invalid_event_id(self):
        with pytest.raises(ValueError, match="event_id must be at least 8 characters"):
            UserEvent(
                event_id="short",
                event_type=EventType.PAGE_VIEW,
                session_id="sess-123",
                device_type=DeviceType.IOS,
            )

    def test_product_view_event(self):
        event = ProductViewEvent(
            event_id=str(uuid.uuid4()),
            session_id="sess-123",
            device_type=DeviceType.ANDROID,
            product_id=456,
            product_name="유기농 바나나",
            price=4900.0,
        )
        assert event.event_type == EventType.PRODUCT_VIEW
        assert event.product_id == 456

    def test_purchase_event(self):
        event = PurchaseEvent(
            event_id=str(uuid.uuid4()),
            session_id="sess-123",
            device_type=DeviceType.IOS,
            order_id=789,
            total_amount=29900.0,
            item_count=3,
            payment_method="card",
        )
        assert event.event_type == EventType.PURCHASE
        assert event.total_amount == 29900.0

    def test_search_event(self):
        event = SearchEvent(
            event_id=str(uuid.uuid4()),
            session_id="sess-123",
            device_type=DeviceType.WEB_MOBILE,
            search_query="바나나",
            result_count=15,
        )
        assert event.search_query == "바나나"
        assert event.result_count == 15

    def test_event_batch(self):
        events = [
            UserEvent(
                event_id=str(uuid.uuid4()),
                event_type=EventType.PAGE_VIEW,
                session_id="sess-123",
                device_type=DeviceType.IOS,
            )
            for _ in range(10)
        ]
        batch = EventBatch(events=events)
        assert batch.event_count == 10

    def test_event_batch_max_size(self):
        with pytest.raises(Exception):
            EventBatch(events=[])  # min_length=1


class TestEventCollectorAPI:
    """Test Event Collector FastAPI endpoints."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_health_check(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_list_event_types(self, client):
        response = client.get("/v1/events/types")
        assert response.status_code == 200
        data = response.json()
        assert "page_view" in data["event_types"]
        assert "purchase" in data["event_types"]

    def test_metrics_endpoint(self, client):
        response = client.get("/metrics")
        assert response.status_code == 200
        assert "events_received_total" in response.text
