"""
Pipeline Metrics & Observability
Prometheus metrics and OpenTelemetry tracing for data pipeline monitoring.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable

from prometheus_client import Counter, Gauge, Histogram, Info


# ─── Pipeline Metrics ─────────────────────────────────────────

PIPELINE_RUNS = Counter(
    "pipeline_runs_total",
    "Total pipeline executions",
    ["pipeline_name", "status"],
)

PIPELINE_DURATION = Histogram(
    "pipeline_duration_seconds",
    "Pipeline execution duration",
    ["pipeline_name"],
    buckets=[1, 5, 10, 30, 60, 120, 300, 600, 1800, 3600],
)

PIPELINE_ROWS_PROCESSED = Counter(
    "pipeline_rows_processed_total",
    "Total rows processed by pipeline",
    ["pipeline_name", "table_name"],
)

PIPELINE_ERRORS = Counter(
    "pipeline_errors_total",
    "Total pipeline errors",
    ["pipeline_name", "error_type"],
)

# ─── Data Quality Metrics ─────────────────────────────────────

DQ_CHECK_STATUS = Gauge(
    "data_quality_check_status",
    "Data quality check status (1=pass, 0=fail)",
    ["check_name", "table_name"],
)

DQ_FRESHNESS_MINUTES = Gauge(
    "data_freshness_minutes",
    "Data freshness in minutes",
    ["table_name"],
)

DQ_NULL_RATE = Gauge(
    "data_null_rate",
    "Null rate for columns",
    ["table_name", "column_name"],
)

DQ_VOLUME_ZSCORE = Gauge(
    "data_volume_zscore",
    "Volume anomaly z-score",
    ["table_name"],
)

# ─── BigQuery Metrics ─────────────────────────────────────────

BQ_BYTES_PROCESSED = Counter(
    "bigquery_bytes_processed_total",
    "Total bytes processed in BigQuery",
    ["query_type"],
)

BQ_QUERY_DURATION = Histogram(
    "bigquery_query_duration_seconds",
    "BigQuery query duration",
    ["query_type"],
    buckets=[0.5, 1, 2, 5, 10, 30, 60, 120],
)

BQ_SLOTS_USED = Gauge(
    "bigquery_slots_used",
    "BigQuery slots currently in use",
)

# ─── Pub/Sub Metrics ──────────────────────────────────────────

PUBSUB_MESSAGES_PUBLISHED = Counter(
    "pubsub_messages_published_total",
    "Total messages published to Pub/Sub",
    ["topic"],
)

PUBSUB_PUBLISH_LATENCY = Histogram(
    "pubsub_publish_latency_seconds",
    "Pub/Sub publish latency",
    ["topic"],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5],
)

# ─── Build Info ───────────────────────────────────────────────

BUILD_INFO = Info("app", "Application build information")
BUILD_INFO.info({
    "version": "1.0.0",
    "component": "ecommerce-data-platform",
})


# ─── Decorators ───────────────────────────────────────────────

def track_pipeline(pipeline_name: str):
    """Decorator to automatically track pipeline execution metrics."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                PIPELINE_RUNS.labels(
                    pipeline_name=pipeline_name, status="success"
                ).inc()
                return result
            except Exception as e:
                PIPELINE_RUNS.labels(
                    pipeline_name=pipeline_name, status="error"
                ).inc()
                PIPELINE_ERRORS.labels(
                    pipeline_name=pipeline_name,
                    error_type=type(e).__name__,
                ).inc()
                raise
            finally:
                duration = time.perf_counter() - start
                PIPELINE_DURATION.labels(pipeline_name=pipeline_name).observe(duration)

        return wrapper

    return decorator


@contextmanager
def track_bigquery_query(query_type: str = "general"):
    """Context manager to track BigQuery query metrics."""
    start = time.perf_counter()
    try:
        yield
    finally:
        duration = time.perf_counter() - start
        BQ_QUERY_DURATION.labels(query_type=query_type).observe(duration)
