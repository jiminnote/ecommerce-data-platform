"""
Pub/Sub Publisher
Publishes user events to Google Cloud Pub/Sub for downstream processing.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from google.api_core import retry_async
from google.cloud import pubsub_v1
from google.cloud.pubsub_v1.types import PubsubMessage

from src.event_collector.models import UserEvent

logger = logging.getLogger(__name__)


class EventPublisher:
    """Publishes user behavior events to Pub/Sub topic.

    Uses batching for high-throughput scenarios and provides
    async publishing with error handling.
    """

    def __init__(self, project_id: str, topic_id: str) -> None:
        self.project_id = project_id
        self.topic_id = topic_id
        self.topic_path = f"projects/{project_id}/topics/{topic_id}"

        # Configure batching for high throughput
        batch_settings = pubsub_v1.types.BatchSettings(
            max_messages=100,
            max_bytes=1024 * 1024,  # 1MB
            max_latency=0.1,  # 100ms
        )
        self.publisher = pubsub_v1.PublisherClient(batch_settings=batch_settings)
        self._publish_count = 0

    async def publish_event(self, event: UserEvent) -> str:
        """Publish a single event to Pub/Sub.

        Args:
            event: The user event to publish.

        Returns:
            The message ID from Pub/Sub.
        """
        data = json.dumps(event.to_bigquery_row()).encode("utf-8")

        # Add attributes for routing and filtering
        attributes = {
            "event_type": event.event_type.value,
            "device_type": event.device_type.value,
        }
        if event.user_id:
            attributes["user_id"] = str(event.user_id)

        future = self.publisher.publish(
            self.topic_path,
            data=data,
            **attributes,
        )
        message_id = future.result(timeout=30)
        self._publish_count += 1

        logger.debug(
            "Published event",
            extra={
                "event_id": event.event_id,
                "event_type": event.event_type.value,
                "message_id": message_id,
            },
        )
        return message_id

    async def publish_batch(self, events: list[UserEvent]) -> list[str]:
        """Publish a batch of events to Pub/Sub.

        Args:
            events: List of user events to publish.

        Returns:
            List of message IDs.
        """
        message_ids = []
        futures = []

        for event in events:
            data = json.dumps(event.to_bigquery_row()).encode("utf-8")
            attributes = {
                "event_type": event.event_type.value,
                "device_type": event.device_type.value,
            }

            future = self.publisher.publish(
                self.topic_path,
                data=data,
                **attributes,
            )
            futures.append(future)

        # Wait for all publishes to complete
        for future in futures:
            try:
                message_id = future.result(timeout=60)
                message_ids.append(message_id)
            except Exception as e:
                logger.error(f"Failed to publish event: {e}")
                message_ids.append("")

        published_count = sum(1 for mid in message_ids if mid)
        logger.info(
            f"Published batch: {published_count}/{len(events)} events",
            extra={"batch_size": len(events), "success_count": published_count},
        )

        self._publish_count += published_count
        return message_ids

    @property
    def publish_count(self) -> int:
        """Total number of successfully published events."""
        return self._publish_count

    def close(self) -> None:
        """Shutdown the publisher client gracefully."""
        self.publisher.stop()
        logger.info(f"Publisher closed. Total published: {self._publish_count}")
