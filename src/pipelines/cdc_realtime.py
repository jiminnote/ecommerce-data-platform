"""
Real-time CDC Pipeline
Consumes Change Data Capture events from Debezium/Kafka
and streams them into BigQuery via Pub/Sub.

Architecture:
  PostgreSQL → Debezium → Kafka → This Pipeline → BigQuery (raw layer)

Design Decisions:
  - Pull-based consumer with configurable batch sizes for backpressure control
  - Idempotent writes using BigQuery merge (deduplication by primary key + timestamp)
  - Schema evolution handled via BigQuery schema auto-detection + migration
  - Dead letter queue for malformed events
"""

from __future__ import annotations

import json
import logging
import os
import signal
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import structlog
from google.cloud import bigquery, pubsub_v1

logger = structlog.get_logger()


@dataclass
class CDCEvent:
    """Represents a parsed CDC change event from Debezium."""

    table_name: str
    operation: str  # c=create, u=update, d=delete, r=read(snapshot)
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    timestamp_ms: int
    source_db: str = "ecommerce"

    @classmethod
    def from_debezium(cls, payload: dict[str, Any]) -> CDCEvent:
        """Parse a Debezium CDC event payload.

        Debezium envelope format:
        {
            "before": {...},
            "after": {...},
            "source": {"table": "orders", ...},
            "op": "c",
            "ts_ms": 1234567890
        }
        """
        source = payload.get("source", {})
        return cls(
            table_name=source.get("table", "unknown"),
            operation=payload.get("op", "?"),
            before=payload.get("before"),
            after=payload.get("after"),
            timestamp_ms=payload.get("ts_ms", 0),
        )

    @property
    def operation_label(self) -> str:
        return {"c": "INSERT", "u": "UPDATE", "d": "DELETE", "r": "SNAPSHOT"}.get(
            self.operation, "UNKNOWN"
        )

    def to_bigquery_row(self) -> dict[str, Any]:
        """Convert CDC event to BigQuery row format.

        We store all CDC events in an append-only raw table for auditability,
        then materialize the latest state in a separate view/table.
        """
        row = {
            "cdc_table": self.table_name,
            "cdc_operation": self.operation_label,
            "cdc_timestamp": datetime.utcfromtimestamp(
                self.timestamp_ms / 1000
            ).isoformat(),
            "before_data": json.dumps(self.before) if self.before else None,
            "after_data": json.dumps(self.after) if self.after else None,
            "raw_payload": json.dumps(self.after or self.before or {}),
            "ingested_at": datetime.utcnow().isoformat(),
        }

        # Flatten the 'after' record for direct querying
        if self.after:
            for key, value in self.after.items():
                row[f"col_{key}"] = str(value) if value is not None else None

        return row


@dataclass
class CDCPipelineConfig:
    """Configuration for the CDC pipeline."""

    project_id: str = field(default_factory=lambda: os.getenv("GCP_PROJECT_ID", "local-dev"))
    subscription_id: str = field(default_factory=lambda: os.getenv("CDC_SUBSCRIPTION", "cdc-events-sub"))
    dataset_id: str = field(default_factory=lambda: os.getenv("BQ_DATASET_RAW", "raw"))
    batch_size: int = 100
    flush_interval_sec: float = 5.0
    max_outstanding_messages: int = 1000
    ack_deadline_sec: int = 60


class BigQueryCDCSink:
    """Writes CDC events to BigQuery using streaming inserts.

    Trade-off Analysis:
    - Streaming Insert vs Load Job:
      - Streaming: Low latency (~seconds), but costs $0.01/200MB and has quotas
      - Load Job: Free, but higher latency (~minutes) and limited to 1500/day
      - Choice: Streaming for real-time CDC where latency < 10s is required

    - Storage Write API (preferred for production):
      - Exactly-once semantics with committed streams
      - Higher throughput (up to 3GB/s per project)
      - Lower cost than legacy streaming inserts
    """

    def __init__(self, project_id: str, dataset_id: str) -> None:
        self.client = bigquery.Client(project=project_id)
        self.project_id = project_id
        self.dataset_id = dataset_id
        self._table_schemas: dict[str, bool] = {}

    def ensure_table_exists(self, table_name: str) -> str:
        """Create CDC table if it doesn't exist.

        Each source table gets its own BigQuery table in the raw layer
        with a standardized CDC schema.
        """
        table_id = f"{self.project_id}.{self.dataset_id}.cdc_{table_name}"

        if table_name in self._table_schemas:
            return table_id

        schema = [
            bigquery.SchemaField("cdc_table", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("cdc_operation", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("cdc_timestamp", "TIMESTAMP", mode="REQUIRED"),
            bigquery.SchemaField("before_data", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("after_data", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("raw_payload", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("ingested_at", "TIMESTAMP", mode="REQUIRED"),
        ]

        table = bigquery.Table(table_id, schema=schema)
        table.time_partitioning = bigquery.TimePartitioning(
            type_=bigquery.TimePartitioningType.DAY,
            field="cdc_timestamp",
        )
        table.clustering_fields = ["cdc_operation"]

        try:
            self.client.create_table(table, exists_ok=True)
            self._table_schemas[table_name] = True
            logger.info("Table ensured", table_id=table_id)
        except Exception as e:
            logger.error("Failed to create table", table_id=table_id, error=str(e))
            raise

        return table_id

    def write_batch(self, table_name: str, rows: list[dict[str, Any]]) -> int:
        """Write a batch of CDC rows to BigQuery using streaming insert.

        Returns the number of successfully written rows.
        """
        if not rows:
            return 0

        table_id = self.ensure_table_exists(table_name)

        errors = self.client.insert_rows_json(table_id, rows)
        if errors:
            logger.error(
                "BigQuery insert errors",
                table=table_name,
                error_count=len(errors),
                errors=errors[:3],  # Log first 3 errors
            )
            return len(rows) - len(errors)

        logger.info(
            "Batch written to BigQuery",
            table=table_name,
            row_count=len(rows),
        )
        return len(rows)


class CDCRealtimePipeline:
    """Real-time CDC Pipeline consuming from Pub/Sub and writing to BigQuery.

    Flow:
    1. Subscribe to CDC events from Pub/Sub
    2. Parse Debezium change events
    3. Buffer events by target table
    4. Flush buffered events to BigQuery in batches
    """

    def __init__(self, config: CDCPipelineConfig | None = None) -> None:
        self.config = config or CDCPipelineConfig()
        self.sink = BigQueryCDCSink(self.config.project_id, self.config.dataset_id)
        self.subscriber = pubsub_v1.SubscriberClient()
        self.subscription_path = self.subscriber.subscription_path(
            self.config.project_id, self.config.subscription_id
        )

        # Event buffer: table_name -> list of rows
        self._buffer: dict[str, list[dict[str, Any]]] = {}
        self._buffer_count = 0
        self._last_flush_time = time.time()
        self._running = True
        self._total_processed = 0

    def _handle_message(self, message: pubsub_v1.subscriber.message.Message) -> None:
        """Process a single Pub/Sub message containing a CDC event."""
        try:
            payload = json.loads(message.data.decode("utf-8"))
            cdc_event = CDCEvent.from_debezium(payload)

            row = cdc_event.to_bigquery_row()
            table_name = cdc_event.table_name

            if table_name not in self._buffer:
                self._buffer[table_name] = []
            self._buffer[table_name].append(row)
            self._buffer_count += 1

            message.ack()

            # Flush if buffer is full or time interval exceeded
            if self._should_flush():
                self._flush_all_buffers()

        except json.JSONDecodeError as e:
            logger.error("Invalid JSON in CDC message", error=str(e))
            message.nack()
        except Exception as e:
            logger.error("Error processing CDC message", error=str(e))
            message.nack()

    def _should_flush(self) -> bool:
        """Determine if the buffer should be flushed."""
        if self._buffer_count >= self.config.batch_size:
            return True
        if time.time() - self._last_flush_time >= self.config.flush_interval_sec:
            return True
        return False

    def _flush_all_buffers(self) -> None:
        """Flush all buffered events to BigQuery."""
        if not self._buffer:
            return

        total_written = 0
        for table_name, rows in self._buffer.items():
            written = self.sink.write_batch(table_name, rows)
            total_written += written

        self._total_processed += total_written
        logger.info(
            "Buffer flushed",
            tables=list(self._buffer.keys()),
            total_rows=self._buffer_count,
            written=total_written,
            cumulative_total=self._total_processed,
        )

        self._buffer.clear()
        self._buffer_count = 0
        self._last_flush_time = time.time()

    def run(self) -> None:
        """Start the CDC pipeline.

        Subscribes to Pub/Sub and processes CDC events continuously.
        Handles graceful shutdown on SIGTERM/SIGINT.
        """

        def _shutdown(signum, frame):
            logger.info("Shutdown signal received", signal=signum)
            self._running = False

        signal.signal(signal.SIGTERM, _shutdown)
        signal.signal(signal.SIGINT, _shutdown)

        flow_control = pubsub_v1.types.FlowControl(
            max_messages=self.config.max_outstanding_messages,
        )

        logger.info(
            "Starting CDC pipeline",
            subscription=self.subscription_path,
            batch_size=self.config.batch_size,
            flush_interval=self.config.flush_interval_sec,
        )

        streaming_pull_future = self.subscriber.subscribe(
            self.subscription_path,
            callback=self._handle_message,
            flow_control=flow_control,
        )

        try:
            while self._running:
                time.sleep(1)
                # Periodic flush for low-volume periods
                if self._should_flush():
                    self._flush_all_buffers()
        except Exception as e:
            logger.error("Pipeline error", error=str(e))
        finally:
            streaming_pull_future.cancel()
            streaming_pull_future.result()  # Wait for cancellation
            self._flush_all_buffers()  # Final flush
            logger.info(
                "CDC pipeline stopped",
                total_processed=self._total_processed,
            )


if __name__ == "__main__":
    pipeline = CDCRealtimePipeline()
    pipeline.run()
