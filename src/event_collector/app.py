"""
Event Collector FastAPI Application
High-throughput REST API for collecting user behavior events and publishing to Pub/Sub.
"""

from __future__ import annotations

import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, Histogram, generate_latest

from src.event_collector.models import EventBatch, EventType, UserEvent
from src.event_collector.publisher import EventPublisher

# ─── Structured Logging ──────────────────────────────────────
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer() if os.getenv("LOG_FORMAT") == "console"
        else structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(
        logging.getLevelName(os.getenv("LOG_LEVEL", "INFO"))
    ),
)

logger = structlog.get_logger()

# ─── Prometheus Metrics ──────────────────────────────────────
EVENTS_RECEIVED = Counter(
    "events_received_total",
    "Total number of events received",
    ["event_type", "device_type"],
)
EVENTS_PUBLISHED = Counter(
    "events_published_total",
    "Total number of events published to Pub/Sub",
    ["status"],
)
REQUEST_LATENCY = Histogram(
    "request_latency_seconds",
    "Request latency in seconds",
    ["method", "endpoint"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
)

# ─── Application Lifecycle ───────────────────────────────────
publisher: EventPublisher | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle - setup and teardown."""
    global publisher

    project_id = os.getenv("GCP_PROJECT_ID", "local-dev")
    topic_id = os.getenv("PUBSUB_TOPIC", "user-events")

    logger.info("Starting Event Collector", project_id=project_id, topic_id=topic_id)

    try:
        publisher = EventPublisher(project_id=project_id, topic_id=topic_id)
        logger.info("Pub/Sub publisher initialized")
    except Exception as e:
        logger.error("Failed to initialize publisher", error=str(e))
        publisher = None

    yield

    if publisher:
        publisher.close()
        logger.info("Publisher shutdown complete")


# ─── FastAPI App ─────────────────────────────────────────────
app = FastAPI(
    title="E-commerce Event Collector",
    description="High-throughput user behavior event ingestion API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


# ─── Middleware ───────────────────────────────────────────────
@app.middleware("http")
async def metrics_middleware(request: Request, call_next) -> Response:
    """Track request latency for Prometheus."""
    start_time = time.perf_counter()
    response = await call_next(request)
    latency = time.perf_counter() - start_time
    REQUEST_LATENCY.labels(
        method=request.method,
        endpoint=request.url.path,
    ).observe(latency)
    return response


# ─── Health & Metrics ────────────────────────────────────────
@app.get("/health")
async def health_check() -> dict[str, Any]:
    """Health check endpoint for Kubernetes liveness/readiness probes."""
    return {
        "status": "healthy",
        "publisher_active": publisher is not None,
        "total_published": publisher.publish_count if publisher else 0,
    }


@app.get("/metrics")
async def metrics() -> Response:
    """Prometheus metrics endpoint."""
    return Response(
        content=generate_latest(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


# ─── Event Ingestion Endpoints ───────────────────────────────
@app.post("/v1/events", status_code=202)
async def ingest_event(event: UserEvent) -> dict[str, str]:
    """Ingest a single user behavior event.

    The event is validated, enriched, and published to Pub/Sub
    for downstream processing into BigQuery.
    """
    if publisher is None:
        raise HTTPException(status_code=503, detail="Publisher not available")

    EVENTS_RECEIVED.labels(
        event_type=event.event_type.value,
        device_type=event.device_type.value,
    ).inc()

    try:
        message_id = await publisher.publish_event(event)
        EVENTS_PUBLISHED.labels(status="success").inc()

        logger.info(
            "Event ingested",
            event_id=event.event_id,
            event_type=event.event_type.value,
            message_id=message_id,
        )

        return {"status": "accepted", "message_id": message_id}

    except Exception as e:
        EVENTS_PUBLISHED.labels(status="error").inc()
        logger.error("Failed to ingest event", event_id=event.event_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to publish event")


@app.post("/v1/events/batch", status_code=202)
async def ingest_event_batch(batch: EventBatch) -> dict[str, Any]:
    """Ingest a batch of user behavior events.

    Supports up to 500 events per batch for efficient bulk ingestion.
    """
    if publisher is None:
        raise HTTPException(status_code=503, detail="Publisher not available")

    for event in batch.events:
        EVENTS_RECEIVED.labels(
            event_type=event.event_type.value,
            device_type=event.device_type.value,
        ).inc()

    try:
        message_ids = await publisher.publish_batch(batch.events)
        success_count = sum(1 for mid in message_ids if mid)
        failed_count = len(message_ids) - success_count

        EVENTS_PUBLISHED.labels(status="success").inc(success_count)
        EVENTS_PUBLISHED.labels(status="error").inc(failed_count)

        logger.info(
            "Batch ingested",
            total=batch.event_count,
            success=success_count,
            failed=failed_count,
        )

        return {
            "status": "accepted",
            "total": batch.event_count,
            "published": success_count,
            "failed": failed_count,
        }

    except Exception as e:
        logger.error("Failed to ingest batch", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to publish batch")


@app.get("/v1/events/types")
async def list_event_types() -> dict[str, list[str]]:
    """List all supported event types."""
    return {"event_types": [e.value for e in EventType]}


def main() -> None:
    """Entry point for running the server."""
    import uvicorn

    uvicorn.run(
        "src.event_collector.app:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8080")),
        workers=int(os.getenv("WORKERS", "4")),
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )


if __name__ == "__main__":
    main()
