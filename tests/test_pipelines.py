"""Tests for pipeline modules."""

from __future__ import annotations

import json
from datetime import date

import pytest

from src.pipelines.cdc_realtime import CDCEvent, CDCPipelineConfig


class TestCDCEvent:
    """Test CDC event parsing and transformation."""

    def test_parse_debezium_insert(self):
        payload = {
            "before": None,
            "after": {
                "order_id": 1,
                "user_id": 42,
                "order_status": "PENDING",
                "total_amount": 29900.00,
            },
            "source": {
                "table": "orders",
                "db": "ecommerce",
            },
            "op": "c",
            "ts_ms": 1700000000000,
        }
        event = CDCEvent.from_debezium(payload)

        assert event.table_name == "orders"
        assert event.operation == "c"
        assert event.operation_label == "INSERT"
        assert event.after["order_id"] == 1
        assert event.before is None

    def test_parse_debezium_update(self):
        payload = {
            "before": {"order_id": 1, "order_status": "PENDING"},
            "after": {"order_id": 1, "order_status": "PAID"},
            "source": {"table": "orders"},
            "op": "u",
            "ts_ms": 1700000001000,
        }
        event = CDCEvent.from_debezium(payload)

        assert event.operation_label == "UPDATE"
        assert event.before["order_status"] == "PENDING"
        assert event.after["order_status"] == "PAID"

    def test_parse_debezium_delete(self):
        payload = {
            "before": {"order_id": 1},
            "after": None,
            "source": {"table": "orders"},
            "op": "d",
            "ts_ms": 1700000002000,
        }
        event = CDCEvent.from_debezium(payload)
        assert event.operation_label == "DELETE"

    def test_to_bigquery_row(self):
        payload = {
            "before": None,
            "after": {"product_id": 10, "name": "바나나", "price": 4900},
            "source": {"table": "products"},
            "op": "c",
            "ts_ms": 1700000000000,
        }
        event = CDCEvent.from_debezium(payload)
        row = event.to_bigquery_row()

        assert row["cdc_table"] == "products"
        assert row["cdc_operation"] == "INSERT"
        assert row["after_data"] is not None
        assert "col_product_id" in row
        assert row["col_name"] == "바나나"

    def test_cdc_pipeline_config_defaults(self):
        config = CDCPipelineConfig()
        assert config.batch_size == 100
        assert config.flush_interval_sec == 5.0
        assert config.max_outstanding_messages == 1000
