"""
Batch ETL Pipeline
Daily batch pipeline that transforms raw data in BigQuery
from the raw layer to staging and mart layers.

Architecture:
  BigQuery (raw) → Transform → BigQuery (staging) → Transform → BigQuery (mart)

Uses BigQuery-native SQL transformations to minimize data movement costs.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import structlog
from google.cloud import bigquery

logger = structlog.get_logger()

SQL_DIR = Path(__file__).parent.parent / "bigquery" / "queries"


@dataclass
class BatchPipelineConfig:
    """Configuration for batch ETL pipeline."""

    project_id: str = field(default_factory=lambda: os.getenv("GCP_PROJECT_ID", "local-dev"))
    raw_dataset: str = field(default_factory=lambda: os.getenv("BQ_DATASET_RAW", "raw"))
    staging_dataset: str = field(default_factory=lambda: os.getenv("BQ_DATASET_STAGING", "staging"))
    mart_dataset: str = field(default_factory=lambda: os.getenv("BQ_DATASET_MART", "mart"))
    location: str = "asia-northeast3"


class BatchPipeline:
    """Daily batch ETL pipeline for BigQuery data transformations.

    Layer Architecture:
    ┌─────────────────────────────────────────────────┐
    │  Raw Layer (raw dataset)                        │
    │  - CDC tables (append-only, partitioned by day) │
    │  - Event tables (user behavior logs)            │
    │  - Source: real-time pipelines                  │
    ├─────────────────────────────────────────────────┤
    │  Staging Layer (staging dataset)                │
    │  - Deduplicated current state                   │
    │  - Data quality validated                       │
    │  - Standardized types and formats               │
    ├─────────────────────────────────────────────────┤
    │  Mart Layer (mart dataset)                      │
    │  - Business-ready aggregated tables             │
    │  - Pre-computed metrics and KPIs                │
    │  - Optimized for analyst queries                │
    └─────────────────────────────────────────────────┘
    """

    def __init__(self, config: BatchPipelineConfig | None = None) -> None:
        self.config = config or BatchPipelineConfig()
        self.client = bigquery.Client(
            project=self.config.project_id,
            location=self.config.location,
        )

    def _run_query(
        self,
        query: str,
        destination_table: str | None = None,
        write_disposition: str = "WRITE_TRUNCATE",
        params: dict[str, Any] | None = None,
    ) -> bigquery.QueryJob:
        """Execute a BigQuery query with optional destination table.

        Args:
            query: SQL query string with optional @param placeholders.
            destination_table: Full table ID for materialized results.
            write_disposition: WRITE_TRUNCATE, WRITE_APPEND, or WRITE_EMPTY.
            params: Query parameters for parameterized queries.
        """
        job_config = bigquery.QueryJobConfig()

        if destination_table:
            job_config.destination = destination_table
            job_config.write_disposition = write_disposition

        if params:
            job_config.query_parameters = [
                bigquery.ScalarQueryParameter(name, "STRING", value)
                for name, value in params.items()
            ]

        logger.info(
            "Running query",
            destination=destination_table,
            query_preview=query[:200],
        )

        job = self.client.query(query, job_config=job_config)
        result = job.result()  # Wait for completion

        logger.info(
            "Query completed",
            destination=destination_table,
            bytes_processed=job.total_bytes_processed,
            rows_affected=result.total_rows if hasattr(result, "total_rows") else None,
            duration_sec=round(
                (job.ended - job.started).total_seconds(), 2
            ) if job.ended and job.started else None,
        )

        return job

    # ─── Raw → Staging Transformations ────────────────────────

    def transform_cdc_to_staging_orders(self, target_date: date) -> bigquery.QueryJob:
        """Materialize latest order state from CDC events.

        Uses ROW_NUMBER() to deduplicate and get the latest version
        of each order from the CDC log.
        """
        query = f"""
        CREATE OR REPLACE TABLE `{self.config.project_id}.{self.config.staging_dataset}.orders`
        PARTITION BY DATE(ordered_at)
        CLUSTER BY order_status, user_id
        AS
        WITH latest_cdc AS (
            SELECT
                *,
                ROW_NUMBER() OVER (
                    PARTITION BY JSON_VALUE(after_data, '$.order_id')
                    ORDER BY cdc_timestamp DESC
                ) AS _row_num
            FROM `{self.config.project_id}.{self.config.raw_dataset}.cdc_orders`
            WHERE cdc_operation != 'DELETE'
        )
        SELECT
            CAST(JSON_VALUE(after_data, '$.order_id') AS INT64) AS order_id,
            CAST(JSON_VALUE(after_data, '$.user_id') AS INT64) AS user_id,
            JSON_VALUE(after_data, '$.order_status') AS order_status,
            CAST(JSON_VALUE(after_data, '$.total_amount') AS FLOAT64) AS total_amount,
            CAST(JSON_VALUE(after_data, '$.delivery_fee') AS FLOAT64) AS delivery_fee,
            JSON_VALUE(after_data, '$.payment_method') AS payment_method,
            JSON_VALUE(after_data, '$.delivery_type') AS delivery_type,
            TIMESTAMP(JSON_VALUE(after_data, '$.ordered_at')) AS ordered_at,
            TIMESTAMP(JSON_VALUE(after_data, '$.delivered_at')) AS delivered_at,
            TIMESTAMP(JSON_VALUE(after_data, '$.updated_at')) AS updated_at,
            cdc_timestamp AS _cdc_timestamp,
            CURRENT_TIMESTAMP() AS _etl_loaded_at
        FROM latest_cdc
        WHERE _row_num = 1
        """
        return self._run_query(query)

    def transform_cdc_to_staging_products(self, target_date: date) -> bigquery.QueryJob:
        """Materialize latest product state from CDC events."""
        query = f"""
        CREATE OR REPLACE TABLE `{self.config.project_id}.{self.config.staging_dataset}.products`
        CLUSTER BY category_l1, storage_type
        AS
        WITH latest_cdc AS (
            SELECT
                *,
                ROW_NUMBER() OVER (
                    PARTITION BY JSON_VALUE(after_data, '$.product_id')
                    ORDER BY cdc_timestamp DESC
                ) AS _row_num
            FROM `{self.config.project_id}.{self.config.raw_dataset}.cdc_products`
            WHERE cdc_operation != 'DELETE'
        )
        SELECT
            CAST(JSON_VALUE(after_data, '$.product_id') AS INT64) AS product_id,
            JSON_VALUE(after_data, '$.name') AS product_name,
            JSON_VALUE(after_data, '$.category_l1') AS category_l1,
            JSON_VALUE(after_data, '$.category_l2') AS category_l2,
            JSON_VALUE(after_data, '$.category_l3') AS category_l3,
            CAST(JSON_VALUE(after_data, '$.price') AS FLOAT64) AS price,
            CAST(JSON_VALUE(after_data, '$.discount_rate') AS FLOAT64) AS discount_rate,
            CAST(JSON_VALUE(after_data, '$.stock_quantity') AS INT64) AS stock_quantity,
            CAST(JSON_VALUE(after_data, '$.is_kurly_only') AS BOOL) AS is_kurly_only,
            JSON_VALUE(after_data, '$.storage_type') AS storage_type,
            cdc_timestamp AS _cdc_timestamp,
            CURRENT_TIMESTAMP() AS _etl_loaded_at
        FROM latest_cdc
        WHERE _row_num = 1
        """
        return self._run_query(query)

    def transform_events_to_staging(self, target_date: date) -> bigquery.QueryJob:
        """Clean and deduplicate user events for the target date."""
        query = f"""
        CREATE OR REPLACE TABLE `{self.config.project_id}.{self.config.staging_dataset}.user_events`
        PARTITION BY DATE(event_timestamp)
        CLUSTER BY event_type, user_id
        AS
        WITH deduplicated AS (
            SELECT
                *,
                ROW_NUMBER() OVER (
                    PARTITION BY event_id
                    ORDER BY ingested_at DESC
                ) AS _row_num
            FROM `{self.config.project_id}.{self.config.raw_dataset}.user_events`
        )
        SELECT
            event_id,
            event_type,
            TIMESTAMP(event_timestamp) AS event_timestamp,
            user_id,
            session_id,
            device_type,
            page_url,
            referrer,
            utm_source,
            utm_medium,
            utm_campaign,
            properties,
            TIMESTAMP(ingested_at) AS ingested_at,
            CURRENT_TIMESTAMP() AS _etl_loaded_at
        FROM deduplicated
        WHERE _row_num = 1
        """
        return self._run_query(query)

    # ─── Staging → Mart Transformations ───────────────────────

    def build_mart_daily_sales(self, target_date: date) -> bigquery.QueryJob:
        """Build daily sales aggregation mart table."""
        query = f"""
        CREATE OR REPLACE TABLE `{self.config.project_id}.{self.config.mart_dataset}.daily_sales`
        PARTITION BY order_date
        AS
        SELECT
            DATE(o.ordered_at) AS order_date,
            o.delivery_type,
            p.category_l1,
            p.storage_type,
            COUNT(DISTINCT o.order_id) AS order_count,
            COUNT(DISTINCT o.user_id) AS unique_customers,
            SUM(o.total_amount) AS total_revenue,
            AVG(o.total_amount) AS avg_order_value,
            SUM(oi.quantity) AS total_items_sold,
            COUNT(DISTINCT CASE WHEN o.order_status = 'CANCELLED' THEN o.order_id END) AS cancelled_orders,
            SAFE_DIVIDE(
                COUNT(DISTINCT CASE WHEN o.order_status = 'CANCELLED' THEN o.order_id END),
                COUNT(DISTINCT o.order_id)
            ) AS cancellation_rate
        FROM `{self.config.project_id}.{self.config.staging_dataset}.orders` o
        LEFT JOIN `{self.config.project_id}.{self.config.staging_dataset}.order_items` oi
            ON o.order_id = oi.order_id
        LEFT JOIN `{self.config.project_id}.{self.config.staging_dataset}.products` p
            ON oi.product_id = p.product_id
        GROUP BY 1, 2, 3, 4
        """
        return self._run_query(query)

    def build_mart_user_funnel(self, target_date: date) -> bigquery.QueryJob:
        """Build user conversion funnel mart table."""
        date_str = target_date.isoformat()
        query = f"""
        CREATE OR REPLACE TABLE `{self.config.project_id}.{self.config.mart_dataset}.daily_funnel`
        PARTITION BY event_date
        AS
        SELECT
            DATE(event_timestamp) AS event_date,
            device_type,
            COUNT(DISTINCT CASE WHEN event_type = 'page_view' THEN session_id END) AS sessions,
            COUNT(DISTINCT CASE WHEN event_type = 'product_view' THEN session_id END) AS product_views,
            COUNT(DISTINCT CASE WHEN event_type = 'add_to_cart' THEN session_id END) AS add_to_carts,
            COUNT(DISTINCT CASE WHEN event_type = 'begin_checkout' THEN session_id END) AS checkouts,
            COUNT(DISTINCT CASE WHEN event_type = 'purchase' THEN session_id END) AS purchases,
            -- Funnel conversion rates
            SAFE_DIVIDE(
                COUNT(DISTINCT CASE WHEN event_type = 'product_view' THEN session_id END),
                COUNT(DISTINCT CASE WHEN event_type = 'page_view' THEN session_id END)
            ) AS view_rate,
            SAFE_DIVIDE(
                COUNT(DISTINCT CASE WHEN event_type = 'add_to_cart' THEN session_id END),
                COUNT(DISTINCT CASE WHEN event_type = 'product_view' THEN session_id END)
            ) AS cart_rate,
            SAFE_DIVIDE(
                COUNT(DISTINCT CASE WHEN event_type = 'purchase' THEN session_id END),
                COUNT(DISTINCT CASE WHEN event_type = 'begin_checkout' THEN session_id END)
            ) AS purchase_rate
        FROM `{self.config.project_id}.{self.config.staging_dataset}.user_events`
        GROUP BY 1, 2
        """
        return self._run_query(query)

    def run(self, target_date: date | None = None) -> None:
        """Execute the full batch ETL pipeline.

        Args:
            target_date: The date to process. Defaults to yesterday.
        """
        if target_date is None:
            target_date = date.today() - timedelta(days=1)

        logger.info("Starting batch pipeline", target_date=target_date.isoformat())
        start_time = datetime.utcnow()

        try:
            # Step 1: Raw → Staging
            logger.info("Phase 1: Raw → Staging transformations")
            self.transform_cdc_to_staging_orders(target_date)
            self.transform_cdc_to_staging_products(target_date)
            self.transform_events_to_staging(target_date)

            # Step 2: Staging → Mart
            logger.info("Phase 2: Staging → Mart transformations")
            self.build_mart_daily_sales(target_date)
            self.build_mart_user_funnel(target_date)

            duration = (datetime.utcnow() - start_time).total_seconds()
            logger.info(
                "Batch pipeline completed",
                target_date=target_date.isoformat(),
                duration_sec=round(duration, 2),
            )

        except Exception as e:
            logger.error(
                "Batch pipeline failed",
                target_date=target_date.isoformat(),
                error=str(e),
            )
            raise


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run batch ETL pipeline")
    parser.add_argument(
        "--date",
        type=str,
        default="yesterday",
        help="Target date (YYYY-MM-DD or 'yesterday')",
    )
    args = parser.parse_args()

    if args.date == "yesterday":
        target = date.today() - timedelta(days=1)
    else:
        target = date.fromisoformat(args.date)

    pipeline = BatchPipeline()
    pipeline.run(target)
