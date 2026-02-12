"""
User Event Processing Pipeline (Apache Beam / Dataflow)
Processes user behavior events from Pub/Sub and loads into BigQuery
using Apache Beam, deployable on Google Cloud Dataflow.

Architecture:
  Pub/Sub → Apache Beam (Dataflow) → BigQuery

Design Decisions:
  - Apache Beam for unified batch/stream processing
  - Windowing: Fixed 1-minute windows for near-real-time aggregation
  - Exactly-once semantics via Beam's built-in deduplication
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any

import apache_beam as beam
from apache_beam.io.gcp.bigquery import BigQueryDisposition, WriteToBigQuery
from apache_beam.io.gcp.pubsub import ReadFromPubSub
from apache_beam.options.pipeline_options import (
    GoogleCloudOptions,
    PipelineOptions,
    StandardOptions,
    WorkerOptions,
)
from apache_beam.transforms.window import FixedWindows


class ParseEventFn(beam.DoFn):
    """Parse and validate raw event JSON from Pub/Sub."""

    def __init__(self) -> None:
        self._parse_errors = beam.metrics.Metrics.counter("events", "parse_errors")
        self._parsed_ok = beam.metrics.Metrics.counter("events", "parsed_ok")

    def process(self, element: bytes):
        try:
            event = json.loads(element.decode("utf-8"))

            # Validate required fields
            required = ["event_id", "event_type", "session_id"]
            if not all(field in event for field in required):
                self._parse_errors.inc()
                yield beam.pvalue.TaggedOutput("dead_letter", element)
                return

            self._parsed_ok.inc()
            yield event
        except json.JSONDecodeError:
            self._parse_errors.inc()
            yield beam.pvalue.TaggedOutput("dead_letter", element)


class EnrichEventFn(beam.DoFn):
    """Enrich events with additional metadata."""

    def process(self, event: dict[str, Any]):
        # Add processing metadata
        event["processed_at"] = datetime.utcnow().isoformat()
        event["beam_pipeline_version"] = "1.0.0"

        # Normalize event_type
        event["event_type"] = event.get("event_type", "unknown").lower()

        # Extract date parts for partitioning
        ts = event.get("event_timestamp", datetime.utcnow().isoformat())
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            event["event_date"] = dt.strftime("%Y-%m-%d")
            event["event_hour"] = dt.hour
        except (ValueError, AttributeError):
            event["event_date"] = datetime.utcnow().strftime("%Y-%m-%d")
            event["event_hour"] = datetime.utcnow().hour

        yield event


class SessionAggregatorFn(beam.DoFn):
    """Aggregate events by session within a window."""

    def process(self, element: tuple[str, list[dict]]):
        session_id, events = element
        event_list = list(events)

        if not event_list:
            return

        yield {
            "session_id": session_id,
            "event_count": len(event_list),
            "event_types": list(set(e.get("event_type", "") for e in event_list)),
            "user_id": event_list[0].get("user_id"),
            "device_type": event_list[0].get("device_type"),
            "first_event_at": min(e.get("event_timestamp", "") for e in event_list),
            "last_event_at": max(e.get("event_timestamp", "") for e in event_list),
            "has_purchase": any(e.get("event_type") == "purchase" for e in event_list),
            "window_start": datetime.utcnow().isoformat(),
        }


# ─── BigQuery Schema ─────────────────────────────────────────

EVENT_TABLE_SCHEMA = {
    "fields": [
        {"name": "event_id", "type": "STRING", "mode": "REQUIRED"},
        {"name": "event_type", "type": "STRING", "mode": "REQUIRED"},
        {"name": "event_timestamp", "type": "TIMESTAMP", "mode": "NULLABLE"},
        {"name": "event_date", "type": "DATE", "mode": "NULLABLE"},
        {"name": "event_hour", "type": "INT64", "mode": "NULLABLE"},
        {"name": "user_id", "type": "INT64", "mode": "NULLABLE"},
        {"name": "session_id", "type": "STRING", "mode": "REQUIRED"},
        {"name": "device_type", "type": "STRING", "mode": "NULLABLE"},
        {"name": "page_url", "type": "STRING", "mode": "NULLABLE"},
        {"name": "referrer", "type": "STRING", "mode": "NULLABLE"},
        {"name": "utm_source", "type": "STRING", "mode": "NULLABLE"},
        {"name": "utm_medium", "type": "STRING", "mode": "NULLABLE"},
        {"name": "utm_campaign", "type": "STRING", "mode": "NULLABLE"},
        {"name": "properties", "type": "STRING", "mode": "NULLABLE"},
        {"name": "processed_at", "type": "TIMESTAMP", "mode": "NULLABLE"},
    ]
}

SESSION_TABLE_SCHEMA = {
    "fields": [
        {"name": "session_id", "type": "STRING", "mode": "REQUIRED"},
        {"name": "event_count", "type": "INT64", "mode": "NULLABLE"},
        {"name": "user_id", "type": "INT64", "mode": "NULLABLE"},
        {"name": "device_type", "type": "STRING", "mode": "NULLABLE"},
        {"name": "first_event_at", "type": "TIMESTAMP", "mode": "NULLABLE"},
        {"name": "last_event_at", "type": "TIMESTAMP", "mode": "NULLABLE"},
        {"name": "has_purchase", "type": "BOOL", "mode": "NULLABLE"},
        {"name": "window_start", "type": "TIMESTAMP", "mode": "NULLABLE"},
    ]
}


def build_pipeline_options(streaming: bool = True) -> PipelineOptions:
    """Build Dataflow pipeline options."""
    project_id = os.getenv("GCP_PROJECT_ID", "local-dev")
    region = os.getenv("GCP_REGION", "asia-northeast3")

    options = PipelineOptions()

    # Standard options
    std_options = options.view_as(StandardOptions)
    std_options.runner = os.getenv("BEAM_RUNNER", "DirectRunner")
    std_options.streaming = streaming

    # GCP options
    gcp_options = options.view_as(GoogleCloudOptions)
    gcp_options.project = project_id
    gcp_options.region = region
    gcp_options.temp_location = f"gs://{project_id}-dataflow-temp/tmp"
    gcp_options.staging_location = f"gs://{project_id}-dataflow-temp/staging"

    # Worker options (for Dataflow)
    worker_options = options.view_as(WorkerOptions)
    worker_options.machine_type = "n1-standard-2"
    worker_options.max_num_workers = 10
    worker_options.autoscaling_algorithm = "THROUGHPUT_BASED"
    worker_options.disk_size_gb = 50

    return options


def run_streaming_pipeline() -> None:
    """Run the streaming event processing pipeline.

    This pipeline:
    1. Reads events from Pub/Sub
    2. Parses and validates events
    3. Enriches with metadata
    4. Writes raw events to BigQuery
    5. Aggregates sessions in 1-minute windows
    6. Writes session aggregations to BigQuery
    """
    project_id = os.getenv("GCP_PROJECT_ID", "local-dev")
    topic = os.getenv("PUBSUB_TOPIC", "user-events")
    raw_dataset = os.getenv("BQ_DATASET_RAW", "raw")

    subscription = f"projects/{project_id}/subscriptions/{topic}-beam-sub"
    event_table = f"{project_id}:{raw_dataset}.user_events"
    session_table = f"{project_id}:{raw_dataset}.session_aggregations"

    options = build_pipeline_options(streaming=True)

    with beam.Pipeline(options=options) as pipeline:
        # Read from Pub/Sub
        raw_events = (
            pipeline
            | "ReadPubSub" >> ReadFromPubSub(subscription=subscription)
        )

        # Parse events (with dead letter queue)
        parsed = (
            raw_events
            | "ParseEvents" >> beam.ParDo(ParseEventFn()).with_outputs("dead_letter", main="events")
        )

        enriched_events = (
            parsed.events
            | "EnrichEvents" >> beam.ParDo(EnrichEventFn())
        )

        # Write raw events to BigQuery
        _ = (
            enriched_events
            | "WriteRawEvents" >> WriteToBigQuery(
                table=event_table,
                schema=EVENT_TABLE_SCHEMA,
                write_disposition=BigQueryDisposition.WRITE_APPEND,
                create_disposition=BigQueryDisposition.CREATE_IF_NEEDED,
                additional_bq_parameters={
                    "timePartitioning": {
                        "type": "DAY",
                        "field": "event_timestamp",
                    },
                    "clustering": {
                        "fields": ["event_type", "device_type"],
                    },
                },
            )
        )

        # Session aggregation in 1-minute windows
        session_aggs = (
            enriched_events
            | "Window" >> beam.WindowInto(FixedWindows(60))
            | "KeyBySession" >> beam.Map(
                lambda e: (e.get("session_id", "unknown"), e)
            )
            | "GroupBySession" >> beam.GroupByKey()
            | "AggregateSession" >> beam.ParDo(SessionAggregatorFn())
        )

        # Write session aggregations
        _ = (
            session_aggs
            | "WriteSessionAggs" >> WriteToBigQuery(
                table=session_table,
                schema=SESSION_TABLE_SCHEMA,
                write_disposition=BigQueryDisposition.WRITE_APPEND,
                create_disposition=BigQueryDisposition.CREATE_IF_NEEDED,
            )
        )

        # Dead letter queue → separate table for investigation
        _ = (
            parsed.dead_letter
            | "DecodeDeadLetter" >> beam.Map(
                lambda x: {
                    "raw_data": x.decode("utf-8") if isinstance(x, bytes) else str(x),
                    "error_timestamp": datetime.utcnow().isoformat(),
                }
            )
            | "WriteDeadLetter" >> WriteToBigQuery(
                table=f"{project_id}:{raw_dataset}.dead_letter_events",
                schema={
                    "fields": [
                        {"name": "raw_data", "type": "STRING", "mode": "REQUIRED"},
                        {"name": "error_timestamp", "type": "TIMESTAMP", "mode": "REQUIRED"},
                    ]
                },
                write_disposition=BigQueryDisposition.WRITE_APPEND,
                create_disposition=BigQueryDisposition.CREATE_IF_NEEDED,
            )
        )


if __name__ == "__main__":
    run_streaming_pipeline()
