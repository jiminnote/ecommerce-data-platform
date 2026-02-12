"""
BigQuery Schema Manager
Manages BigQuery dataset and table schemas with version control
and migration support.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import structlog
from google.cloud import bigquery

logger = structlog.get_logger()


@dataclass
class DatasetConfig:
    """Configuration for a BigQuery dataset."""

    dataset_id: str
    description: str
    location: str = "asia-northeast3"
    default_table_expiration_ms: int | None = None
    labels: dict[str, str] = field(default_factory=dict)


class SchemaManager:
    """Manages BigQuery datasets, tables, and schema migrations.

    Responsibilities:
    - Create and configure datasets (raw, staging, mart)
    - Define and apply table schemas
    - Handle schema evolution (add columns, change types)
    - Manage partitioning and clustering strategies
    """

    def __init__(self, project_id: str, location: str = "asia-northeast3") -> None:
        self.project_id = project_id
        self.location = location
        self.client = bigquery.Client(project=project_id, location=location)

    def create_datasets(self) -> None:
        """Create all required datasets for the data platform."""
        datasets = [
            DatasetConfig(
                dataset_id="raw",
                description="Raw layer - append-only CDC and event data",
                default_table_expiration_ms=90 * 24 * 3600 * 1000,  # 90 days
                labels={"layer": "raw", "team": "data-platform"},
            ),
            DatasetConfig(
                dataset_id="staging",
                description="Staging layer - cleaned and deduplicated data",
                labels={"layer": "staging", "team": "data-platform"},
            ),
            DatasetConfig(
                dataset_id="mart",
                description="Mart layer - business-ready aggregated tables",
                labels={"layer": "mart", "team": "data-platform"},
            ),
            DatasetConfig(
                dataset_id="monitoring",
                description="Data quality monitoring and observability",
                labels={"layer": "monitoring", "team": "data-platform"},
            ),
        ]

        for ds_config in datasets:
            self._create_dataset(ds_config)

    def _create_dataset(self, config: DatasetConfig) -> None:
        """Create a single BigQuery dataset."""
        dataset_id = f"{self.project_id}.{config.dataset_id}"
        dataset = bigquery.Dataset(dataset_id)
        dataset.location = config.location
        dataset.description = config.description
        dataset.labels = config.labels

        if config.default_table_expiration_ms:
            dataset.default_table_expiration_ms = config.default_table_expiration_ms

        try:
            self.client.create_dataset(dataset, exists_ok=True)
            logger.info("Dataset created/verified", dataset_id=dataset_id)
        except Exception as e:
            logger.error("Failed to create dataset", dataset_id=dataset_id, error=str(e))
            raise

    def create_raw_tables(self) -> None:
        """Create tables in the raw layer."""
        self._create_table(
            dataset="raw",
            table_name="user_events",
            schema=[
                bigquery.SchemaField("event_id", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("event_type", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("event_timestamp", "TIMESTAMP"),
                bigquery.SchemaField("user_id", "INT64"),
                bigquery.SchemaField("session_id", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("device_type", "STRING"),
                bigquery.SchemaField("device_id", "STRING"),
                bigquery.SchemaField("app_version", "STRING"),
                bigquery.SchemaField("page_url", "STRING"),
                bigquery.SchemaField("referrer", "STRING"),
                bigquery.SchemaField("utm_source", "STRING"),
                bigquery.SchemaField("utm_medium", "STRING"),
                bigquery.SchemaField("utm_campaign", "STRING"),
                bigquery.SchemaField("properties", "STRING"),  # JSON string
                bigquery.SchemaField("ingested_at", "TIMESTAMP"),
            ],
            partition_field="event_timestamp",
            clustering_fields=["event_type", "device_type"],
        )

        # CDC tables
        for table_name in ["users", "products", "orders", "order_items"]:
            self._create_cdc_table(table_name)

    def _create_cdc_table(self, source_table: str) -> None:
        """Create a CDC table for a given source table."""
        self._create_table(
            dataset="raw",
            table_name=f"cdc_{source_table}",
            schema=[
                bigquery.SchemaField("cdc_table", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("cdc_operation", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("cdc_timestamp", "TIMESTAMP", mode="REQUIRED"),
                bigquery.SchemaField("before_data", "STRING"),
                bigquery.SchemaField("after_data", "STRING"),
                bigquery.SchemaField("raw_payload", "STRING"),
                bigquery.SchemaField("ingested_at", "TIMESTAMP", mode="REQUIRED"),
            ],
            partition_field="cdc_timestamp",
            clustering_fields=["cdc_operation"],
        )

    def _create_table(
        self,
        dataset: str,
        table_name: str,
        schema: list[bigquery.SchemaField],
        partition_field: str | None = None,
        clustering_fields: list[str] | None = None,
    ) -> None:
        """Create a BigQuery table with optional partitioning and clustering."""
        table_id = f"{self.project_id}.{dataset}.{table_name}"
        table = bigquery.Table(table_id, schema=schema)

        if partition_field:
            table.time_partitioning = bigquery.TimePartitioning(
                type_=bigquery.TimePartitioningType.DAY,
                field=partition_field,
            )

        if clustering_fields:
            table.clustering_fields = clustering_fields

        try:
            self.client.create_table(table, exists_ok=True)
            logger.info(
                "Table created/verified",
                table_id=table_id,
                partition=partition_field,
                clustering=clustering_fields,
            )
        except Exception as e:
            logger.error("Failed to create table", table_id=table_id, error=str(e))
            raise

    def create_monitoring_views(self) -> None:
        """Create monitoring views for pipeline observability."""
        # Pipeline freshness view
        freshness_query = f"""
        CREATE OR REPLACE VIEW `{self.project_id}.monitoring.pipeline_freshness` AS
        SELECT
            'user_events' AS table_name,
            MAX(ingested_at) AS last_ingested_at,
            TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), MAX(ingested_at), MINUTE) AS freshness_minutes,
            COUNT(*) AS total_rows,
            COUNT(DISTINCT DATE(event_timestamp)) AS date_coverage
        FROM `{self.project_id}.raw.user_events`

        UNION ALL

        SELECT
            'cdc_orders' AS table_name,
            MAX(ingested_at) AS last_ingested_at,
            TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), MAX(ingested_at), MINUTE) AS freshness_minutes,
            COUNT(*) AS total_rows,
            COUNT(DISTINCT DATE(cdc_timestamp)) AS date_coverage
        FROM `{self.project_id}.raw.cdc_orders`
        """
        self.client.query(freshness_query).result()
        logger.info("Monitoring views created")

    def setup_all(self) -> None:
        """Run full schema setup - datasets, tables, and views."""
        logger.info("Starting full schema setup", project_id=self.project_id)
        self.create_datasets()
        self.create_raw_tables()
        self.create_monitoring_views()
        logger.info("Schema setup complete")


if __name__ == "__main__":
    import os

    project_id = os.getenv("GCP_PROJECT_ID", "local-dev")
    manager = SchemaManager(project_id=project_id)
    manager.setup_all()
