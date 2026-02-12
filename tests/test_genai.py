"""Tests for GenAI modules."""

from __future__ import annotations

import pytest

from src.genai.data_quality_agent import DataQualityCheck


class TestDataQualityCheck:
    """Test data quality check models."""

    def test_check_pass(self):
        check = DataQualityCheck(
            check_name="freshness",
            table_name="user_events",
            status="PASS",
            metric_value=5.0,
            threshold=30.0,
            details="Data is 5 minutes fresh",
        )
        assert check.status == "PASS"
        assert check.metric_value < check.threshold

    def test_check_fail(self):
        check = DataQualityCheck(
            check_name="freshness",
            table_name="user_events",
            status="FAIL",
            metric_value=45.0,
            threshold=30.0,
            details="Data is 45 minutes old",
        )
        assert check.status == "FAIL"
        assert check.metric_value > check.threshold

    def test_check_to_dict(self):
        check = DataQualityCheck(
            check_name="volume_anomaly",
            table_name="cdc_orders",
            status="WARN",
            metric_value=2.1,
            threshold=2.0,
        )
        d = check.to_dict()
        assert d["check_name"] == "volume_anomaly"
        assert d["table_name"] == "cdc_orders"
        assert "checked_at" in d

    def test_check_without_metric(self):
        check = DataQualityCheck(
            check_name="schema_check",
            table_name="products",
            status="PASS",
            details="Schema matches expected definition",
        )
        assert check.metric_value is None
        assert check.threshold is None
