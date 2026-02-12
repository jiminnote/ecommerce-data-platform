"""
QuickPay Daily Metrics DAG

매일 새벽 dbt 모델 빌드 → 데이터 품질 검증 → 대시보드 리프레시
파이프라인 흐름:
  dbt_staging → dbt_mart → quality_check → dashboard_refresh → daily_summary

Why Airflow?
→ 토스/핀테크 환경에서는 "정확한 시점에 정확한 데이터"가 핵심.
  Cron으로는 DAG 간 의존성, 재시도, 알림 관리가 불가능.
  Airflow는 데이터 파이프라인의 "실행 보장"을 제공.
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from airflow.providers.slack.operators.slack_webhook import SlackWebhookOperator
from airflow.utils.trigger_rule import TriggerRule

# ─── DAG 기본 설정 ──────────────────────────────────────────
default_args = {
    "owner": "quickpay-dataops",
    "depends_on_past": False,
    "email": ["data-team@quickpay.io"],
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(hours=1),
}

dag = DAG(
    dag_id="quickpay_daily_metrics",
    default_args=default_args,
    description="QuickPay 일별 지표 집계 파이프라인",
    schedule_interval="0 2 * * *",  # 매일 새벽 2시
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["quickpay", "daily", "metrics", "production"],
    max_active_runs=1,
)


# ─── Task 1: dbt Staging 빌드 ──────────────────────────────
dbt_staging = BashOperator(
    task_id="dbt_run_staging",
    bash_command=(
        "cd /opt/airflow/dbt/quickpay && "
        "dbt run --select staging --target prod "
        "--vars '{\"run_date\": \"{{ ds }}\"}'"
    ),
    dag=dag,
)

# ─── Task 2: dbt Mart 빌드 ─────────────────────────────────
dbt_mart = BashOperator(
    task_id="dbt_run_mart",
    bash_command=(
        "cd /opt/airflow/dbt/quickpay && "
        "dbt run --select mart --target prod "
        "--vars '{\"run_date\": \"{{ ds }}\"}'"
    ),
    dag=dag,
)

# ─── Task 3: dbt Test (스키마 테스트) ───────────────────────
dbt_test = BashOperator(
    task_id="dbt_test",
    bash_command=(
        "cd /opt/airflow/dbt/quickpay && "
        "dbt test --target prod "
        "--vars '{\"run_date\": \"{{ ds }}\"}'"
    ),
    dag=dag,
)


# ─── Task 4: Great Expectations 데이터 품질 검증 ────────────
def _run_quality_checks(**context):
    """Airflow context에서 품질 검증 실행."""
    from portfolio.data_quality.quality_runner import run_all_checks

    partition_date = context["ds"]
    results = run_all_checks(partition_date=partition_date)

    # XCom으로 결과 전달
    context["ti"].xcom_push(key="quality_results", value=results)
    return results


quality_check = PythonOperator(
    task_id="data_quality_check",
    python_callable=_run_quality_checks,
    dag=dag,
)

# ─── Task 5: Tableau 대시보드 리프레시 ──────────────────────
dashboard_refresh = BashOperator(
    task_id="dashboard_refresh",
    bash_command=(
        'curl -X POST "https://tableau.quickpay.internal/api/3.19/sites/quickpay/extracts" '
        '-H "X-Tableau-Auth: {{ var.value.tableau_token }}" '
        '-d \'{"extractRefreshRequest": {"datasource": {"id": "quickpay-daily-metrics"}}}\''
    ),
    dag=dag,
)


# ─── Task 6: 완료 알림 ─────────────────────────────────────
def _build_summary_message(**context):
    """파이프라인 실행 결과 요약 메시지 생성."""
    ds = context["ds"]
    quality_results = context["ti"].xcom_pull(
        key="quality_results", task_ids="data_quality_check"
    )

    total_checks = len(quality_results) if quality_results else 0
    passed = sum(1 for r in (quality_results or []) if r.get("success"))
    failed = total_checks - passed

    status = "✅ 정상" if failed == 0 else f"⚠️ {failed}건 실패"

    return (
        f"📊 *QuickPay Daily Metrics Pipeline 완료*\n"
        f"• 실행일: {ds}\n"
        f"• 상태: {status}\n"
        f"• 품질 검증: {passed}/{total_checks} 통과\n"
        f"• 대시보드: <https://tableau.quickpay.internal|확인>"
    )


success_alert = SlackWebhookOperator(
    task_id="pipeline_success_alert",
    slack_webhook_conn_id="slack_data_alert",
    message=_build_summary_message,
    channel="#data-daily-summary",
    trigger_rule=TriggerRule.ALL_SUCCESS,
    dag=dag,
)

# 실패 시 알림
failure_alert = SlackWebhookOperator(
    task_id="pipeline_failure_alert",
    slack_webhook_conn_id="slack_data_alert",
    message=(
        "🚨 *QuickPay Daily Metrics Pipeline 실패*\n"
        "• 실행일: {{ ds }}\n"
        "• 실패 Task: {{ task_instance.task_id }}\n"
        "• 로그: {{ task_instance.log_url }}"
    ),
    channel="#data-alert-critical",
    trigger_rule=TriggerRule.ONE_FAILED,
    dag=dag,
)


# ─── DAG Dependencies ──────────────────────────────────────
dbt_staging >> dbt_mart >> dbt_test >> quality_check >> dashboard_refresh
dashboard_refresh >> [success_alert, failure_alert]
