"""
Fake Event Generator
Generates realistic e-commerce user behavior events for testing.
"""

from __future__ import annotations

import json
import random
import uuid
from datetime import datetime, timedelta

import click
from faker import Faker

fake = Faker("ko_KR")

CATEGORIES = {
    "과일": ["열대과일", "국내과일", "수입과일"],
    "채소": ["뿌리채소", "잎채소", "과일채소"],
    "정육": ["소고기", "돼지고기", "닭고기"],
    "수산": ["생선", "조개", "해조류"],
    "간식": ["과자", "초콜릿", "아이스크림"],
    "음료": ["주스", "탄산", "커피"],
}

EVENT_TYPES = [
    "page_view", "product_view", "product_click",
    "add_to_cart", "remove_from_cart", "begin_checkout",
    "purchase", "search", "wishlist_add", "app_open",
]

DEVICES = ["ios", "android", "web_mobile", "web_desktop"]
PAGES = ["/", "/categories", "/search", "/cart", "/mypage", "/orders"]


def generate_event(user_id: int | None = None) -> dict:
    """Generate a single random user event."""
    event_type = random.choices(
        EVENT_TYPES,
        weights=[30, 25, 15, 10, 3, 5, 3, 5, 2, 2],
        k=1,
    )[0]

    event = {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "event_timestamp": (
            datetime.utcnow() - timedelta(seconds=random.randint(0, 86400))
        ).isoformat(),
        "user_id": user_id or random.randint(1, 10000),
        "session_id": f"sess-{uuid.uuid4().hex[:12]}",
        "device_type": random.choice(DEVICES),
        "device_id": f"device-{uuid.uuid4().hex[:8]}",
        "app_version": f"3.{random.randint(0,9)}.{random.randint(0,99)}",
        "page_url": random.choice(PAGES),
        "utm_source": random.choice([None, "google", "naver", "kakao", "instagram"]),
        "properties": {},
    }

    # Add event-specific properties
    if event_type in ("product_view", "product_click", "add_to_cart"):
        cat = random.choice(list(CATEGORIES.keys()))
        event["properties"] = {
            "product_id": random.randint(1, 5000),
            "product_name": f"{fake.word()} {random.choice(CATEGORIES[cat])}",
            "category": cat,
            "price": random.choice([3900, 4900, 8900, 12900, 15900, 29900]),
        }
    elif event_type == "search":
        event["properties"] = {
            "search_query": random.choice(["바나나", "우유", "닭가슴살", "아보카도", "감귤", "계란"]),
            "result_count": random.randint(0, 200),
        }
    elif event_type == "purchase":
        event["properties"] = {
            "order_id": random.randint(100000, 999999),
            "total_amount": random.randint(10000, 100000),
            "item_count": random.randint(1, 15),
            "payment_method": random.choice(["card", "kakao_pay", "naver_pay", "toss"]),
            "delivery_type": random.choice(["DAWN", "SAME_DAY", "NEXT_DAY"]),
        }

    return event


@click.command()
@click.option("--count", default=100, help="Number of events to generate")
@click.option("--output", default="-", help="Output file (- for stdout)")
@click.option("--format", "fmt", default="jsonl", type=click.Choice(["jsonl", "json"]))
def main(count: int, output: str, fmt: str):
    """Generate fake e-commerce events for testing."""
    events = [generate_event() for _ in range(count)]

    if fmt == "json":
        result = json.dumps(events, ensure_ascii=False, indent=2)
    else:
        result = "\n".join(json.dumps(e, ensure_ascii=False) for e in events)

    if output == "-":
        click.echo(result)
    else:
        with open(output, "w") as f:
            f.write(result)
        click.echo(f"✅ Generated {count} events → {output}")


if __name__ == "__main__":
    main()
