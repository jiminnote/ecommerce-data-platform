"""
Daily Batch ETL DAG
Runs the batch pipeline daily at 06:00 KST to process yesterday's data.
Transforms raw → staging → mart layers in BigQuery.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.google.cloud.operators.bigquery import (
    BigQueryCheckOperator,
    BigQueryInsertJobOperator,
)
from airflow.providers.google.cloud.sensors.bigquery import (
    BigQueryTableExistenceSensor,
)

default_args = {
    "owner": "data-platform",
    "depends_on_past": False,
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "email": ["data-platform@your-company.com"],
}

with DAG(
    dag_id="daily_batch_etl",
    default_args=default_args,
    description="Daily batch ETL: raw → staging → mart in BigQuery",
    schedule_interval="0 21 * * *",  # 06:00 KST = 21:00 UTC (previous day)
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["data-platform", "batch", "bigquery"],
) as dag:

    # ─── Wait for raw data availability ───────────────────────
    check_raw_events = BigQueryTableExistenceSensor(
        task_id="check_raw_events_exist",
        project_id="{{ var.value.GCP_PROJECT_ID }}",
        dataset_id="raw",
        table_id="user_events",
        poke_interval=60,
        timeout=300,
    )

    # ─── Raw → Staging: Orders ────────────────────────────────
    staging_orders = BigQueryInsertJobOperator(
        task_id="transform_staging_orders",
        configuration={
            "query": {
                "query": """
                CREATE OR REPLACE TABLE `{{ var.value.GCP_PROJECT_ID }}.staging.orders`
                PARTITION BY DATE(ordered_at)
                CLUSTER BY order_status, user_id
                AS
                WITH latest_cdc AS (
                    SELECT *,
                        ROW_NUMBER() OVER (
                            PARTITION BY JSON_VALUE(after_data, '$.order_id')
                            ORDER BY cdc_timestamp DESC
                        ) AS _rn
                    FROM `{{ var.value.GCP_PROJECT_ID }}.raw.cdc_orders`
                    WHERE cdc_operation != 'DELETE'
                )
                SELECT
                    CAST(JSON_VALUE(after_data, '$.order_id') AS INT64) AS order_id,
                    CAST(JSON_VALUE(after_data, '$.user_id') AS INT64) AS user_id,
                    JSON_VALUE(after_data, '$.order_status') AS order_status,
                    CAST(JSON_VALUE(after_data, '$.total_amount') AS FLOAT64) AS total_amount,
                    JSON_VALUE(after_data, '$.delivery_type') AS delivery_type,
                    TIMESTAMP(JSON_VALUE(after_data, '$.ordered_at')) AS ordered_at,
                    CURRENT_TIMESTAMP() AS _etl_loaded_at
                FROM latest_cdc WHERE _rn = 1
                """,
                "useLegacySql": False,
            }
        },
        location="asia-northeast3",
    )

    # ─── Raw → Staging: User Events ──────────────────────────
    staging_events = BigQueryInsertJobOperator(
        task_id="transform_staging_events",
        configuration={
            "query": {
                "query": """
                CREATE OR REPLACE TABLE `{{ var.value.GCP_PROJECT_ID }}.staging.user_events`
                PARTITION BY DATE(event_timestamp)
                CLUSTER BY event_type, user_id
                AS
                SELECT DISTINCT *
                FROM `{{ var.value.GCP_PROJECT_ID }}.raw.user_events`
                """,
                "useLegacySql": False,
            }
        },
        location="asia-northeast3",
    )

    # ─── Staging → Mart: Daily Sales ─────────────────────────
    mart_daily_sales = BigQueryInsertJobOperator(
        task_id="build_mart_daily_sales",
        configuration={
            "query": {
                "query": """
                CREATE OR REPLACE TABLE `{{ var.value.GCP_PROJECT_ID }}.mart.daily_sales`
                PARTITION BY order_date
                AS
                SELECT
                    DATE(ordered_at) AS order_date,
                    delivery_type,
                    COUNT(DISTINCT order_id) AS order_count,
                    COUNT(DISTINCT user_id) AS unique_customers,
                    SUM(total_amount) AS total_revenue,
                    AVG(total_amount) AS avg_order_value
                FROM `{{ var.value.GCP_PROJECT_ID }}.staging.orders`
                WHERE order_status NOT IN ('CANCELLED', 'REFUNDED')
                GROUP BY 1, 2
                """,
                "useLegacySql": False,
            }
        },
        location="asia-northeast3",
    )

    # ─── Staging → Mart: Funnel ──────────────────────────────
    mart_funnel = BigQueryInsertJobOperator(
        task_id="build_mart_funnel",
        configuration={
            "query": {
                "query": """
                CREATE OR REPLACE TABLE `{{ var.value.GCP_PROJECT_ID }}.mart.daily_funnel`
                PARTITION BY event_date
                AS
                SELECT
                    DATE(event_timestamp) AS event_date,
                    device_type,
                    COUNTIF(event_type = 'page_view') AS page_views,
                    COUNTIF(event_type = 'product_view') AS product_views,
                    COUNTIF(event_type = 'add_to_cart') AS add_to_carts,
                    COUNTIF(event_type = 'purchase') AS purchases,
                    SAFE_DIVIDE(
                        COUNTIF(event_type = 'purchase'),
                        COUNTIF(event_type = 'page_view')
                    ) AS overall_conversion
                FROM `{{ var.value.GCP_PROJECT_ID }}.staging.user_events`
                GROUP BY 1, 2
                """,
                "useLegacySql": False,
            }
        },
        location="asia-northeast3",
    )

    # ─── Data Quality Check ──────────────────────────────────
    quality_check = BigQueryCheckOperator(
        task_id="quality_check_row_count",
        sql="""
        SELECT COUNT(*) > 0
        FROM `{{ var.value.GCP_PROJECT_ID }}.mart.daily_sales`
        WHERE order_date = DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY)
        """,
        use_legacy_sql=False,
        location="asia-northeast3",
    )

    # ─── DAG Dependencies ────────────────────────────────────
    check_raw_events >> [staging_orders, staging_events]
    staging_orders >> mart_daily_sales
    staging_events >> mart_funnel
    [mart_daily_sales, mart_funnel] >> quality_check
