"""
Data Quality Check DAG
Runs GenAI-powered data quality agent every 30 minutes.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

default_args = {
    "owner": "data-platform",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
}


def run_quality_agent(**kwargs):
    """Run the GenAI data quality agent."""
    import asyncio
    from src.genai.data_quality_agent import DataQualityAgent

    agent = DataQualityAgent()
    report = asyncio.run(agent.run_full_check())

    # Push results to XCom for downstream tasks
    kwargs["ti"].xcom_push(key="quality_status", value={
        "total_checks": len(agent.checks),
        "passed": sum(1 for c in agent.checks if c.status == "PASS"),
        "warnings": sum(1 for c in agent.checks if c.status == "WARN"),
        "failed": sum(1 for c in agent.checks if c.status == "FAIL"),
        "ai_analysis_preview": report.ai_analysis[:500],
    })

    # Fail the task if critical issues found
    critical_failures = [
        c for c in agent.checks
        if c.status == "FAIL" and c.check_name in ("freshness", "volume_anomaly")
    ]
    if critical_failures:
        raise Exception(
            f"Critical data quality failures: "
            f"{[c.check_name for c in critical_failures]}"
        )


with DAG(
    dag_id="data_quality_check",
    default_args=default_args,
    description="GenAI-powered data quality monitoring",
    schedule_interval="*/30 * * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["data-platform", "quality", "genai"],
) as dag:

    quality_check = PythonOperator(
        task_id="run_genai_quality_agent",
        python_callable=run_quality_agent,
    )
