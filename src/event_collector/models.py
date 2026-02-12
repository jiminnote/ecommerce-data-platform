"""
Event Collector Models
Pydantic models for user behavior events in e-commerce platform.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class EventType(str, Enum):
    """Supported user behavior event types."""

    PAGE_VIEW = "page_view"
    PRODUCT_VIEW = "product_view"
    PRODUCT_CLICK = "product_click"
    ADD_TO_CART = "add_to_cart"
    REMOVE_FROM_CART = "remove_from_cart"
    BEGIN_CHECKOUT = "begin_checkout"
    PURCHASE = "purchase"
    SEARCH = "search"
    SEARCH_CLICK = "search_click"
    WISHLIST_ADD = "wishlist_add"
    REVIEW_WRITE = "review_write"
    APP_OPEN = "app_open"
    APP_CLOSE = "app_close"
    PUSH_CLICK = "push_click"
    BANNER_CLICK = "banner_click"


class DeviceType(str, Enum):
    """Device types."""

    IOS = "ios"
    ANDROID = "android"
    WEB_MOBILE = "web_mobile"
    WEB_DESKTOP = "web_desktop"


class UserEvent(BaseModel):
    """Core user behavior event schema.

    Follows a structure similar to GA4 event model,
    adapted for e-commerce specific needs.
    """

    event_id: str = Field(..., description="Unique event identifier (UUID v4)")
    event_type: EventType
    event_timestamp: datetime = Field(default_factory=datetime.utcnow)

    # User context
    user_id: int | None = Field(None, description="Authenticated user ID")
    session_id: str = Field(..., description="Session identifier")
    device_type: DeviceType
    device_id: str | None = None
    app_version: str | None = None

    # Page context
    page_url: str | None = None
    referrer: str | None = None
    utm_source: str | None = None
    utm_medium: str | None = None
    utm_campaign: str | None = None

    # Event-specific properties
    properties: dict[str, Any] = Field(default_factory=dict)

    @field_validator("event_id")
    @classmethod
    def validate_event_id(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("event_id must be at least 8 characters")
        return v

    def to_bigquery_row(self) -> dict[str, Any]:
        """Convert to BigQuery-compatible row format."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "event_timestamp": self.event_timestamp.isoformat(),
            "user_id": self.user_id,
            "session_id": self.session_id,
            "device_type": self.device_type.value,
            "device_id": self.device_id,
            "app_version": self.app_version,
            "page_url": self.page_url,
            "referrer": self.referrer,
            "utm_source": self.utm_source,
            "utm_medium": self.utm_medium,
            "utm_campaign": self.utm_campaign,
            "properties": str(self.properties),
            "ingested_at": datetime.utcnow().isoformat(),
        }


class ProductViewEvent(UserEvent):
    """Specialized event for product views."""

    event_type: EventType = EventType.PRODUCT_VIEW
    product_id: int
    product_name: str | None = None
    category: str | None = None
    price: float | None = None


class PurchaseEvent(UserEvent):
    """Specialized event for purchases."""

    event_type: EventType = EventType.PURCHASE
    order_id: int
    total_amount: float
    item_count: int
    payment_method: str | None = None


class SearchEvent(UserEvent):
    """Specialized event for search actions."""

    event_type: EventType = EventType.SEARCH
    search_query: str
    result_count: int = 0
    filters_applied: dict[str, Any] = Field(default_factory=dict)


class EventBatch(BaseModel):
    """Batch of events for bulk ingestion."""

    events: list[UserEvent] = Field(..., min_length=1, max_length=500)
    client_timestamp: datetime = Field(default_factory=datetime.utcnow)

    @property
    def event_count(self) -> int:
        return len(self.events)
