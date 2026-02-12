"""
QuickPay 데이터 품질 전용 DAG

일 4회 (06:00, 12:00, 18:00, 00:00) 데이터 품질 검증을 수행.
Daily Metrics DAG과 분리한 이유:
→ 품질 검증은 메트릭 파이프라인과 독립적으로 동작해야 함.
  Daily DAG이 실패해도 품질 모니터링은 계속되어야 하며,
  실시간에 가까운 품질 감시가 필요.

Why 별도 DAG?
→ 토스에서는 결제 데이터 이상을 "빠르게" 감지하는 것이 핵심.
  1일 1회 검증만으로는 오후에 발생한 이상을 다음 날까지 모름.
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import BranchPythonOperator, PythonOperator
from airflow.providers.slack.operators.slack_webhook import SlackWebhookOperator
from airflow.utils.trigger_rule import TriggerRule

default_args = {
    "owner": "quickpay-dataops",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=3),
    "execution_timeout": timedelta(minutes=30),
}

dag = DAG(
    dag_id="quickpay_quality_check",
    default_args=default_args,
    description="QuickPay 데이터 품질 실시간 모니터링",
    schedule_interval="0 0,6,12,18 * * *",  # 6시간마다
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["quickpay", "quality", "monitoring"],
    max_active_runs=1,
)


# ─── Task 1: 이벤트 로그 품질 검증 ─────────────────────────
def _check_events(**context):
    """이벤트 로그 테이블 품질 검증."""
    from portfolio.data_quality.quality_runner import run_quality_check

    result = run_quality_check(
        suite_name="quickpay_events_suite",
        table_name="events",
        partition_date=context["ds"],
    )
    context["ti"].xcom_push(key="events_result", value=result)
    return result


check_events = PythonOperator(
    task_id="check_events_quality",
    python_callable=_check_events,
    dag=dag,
)


# ─── Task 2: 트랜잭션 품질 검증 ────────────────────────────
def _check_transactions(**context):
    """결제/송금 트랜잭션 테이블 품질 검증."""
    from portfolio.data_quality.quality_runner import run_quality_check

    result = run_quality_check(
        suite_name="quickpay_transactions_suite",
        table_name="transactions",
        partition_date=context["ds"],
    )
    context["ti"].xcom_push(key="txn_result", value=result)
    return result


check_transactions = PythonOperator(
    task_id="check_transactions_quality",
    python_callable=_check_transactions,
    dag=dag,
)


# ─── Task 3: 볼륨 이상 감지 (급감/급증) ────────────────────
def _check_volume_anomaly(**context):
    """
    이벤트 볼륨 이상 감지.
    전일 동시간 대비 ±50% 이상 차이나면 Alert.
    """
    from google.cloud import bigquery

    client = bigquery.Client()
    query = f"""
        WITH today AS (
            SELECT COUNT(*) AS cnt
            FROM `quickpay-data.analytics.events`
            WHERE DATE(event_timestamp) = '{context["ds"]}'
        ),
        yesterday AS (
            SELECT COUNT(*) AS cnt
            FROM `quickpay-data.analytics.events`
            WHERE DATE(event_timestamp) = DATE_SUB('{context["ds"]}', INTERVAL 1 DAY)
        )
        SELECT
            today.cnt AS today_count,
            yesterday.cnt AS yesterday_count,
            SAFE_DIVIDE(today.cnt - yesterday.cnt, yesterday.cnt) * 100 AS change_pct
        FROM today, yesterday
    """

    result = list(client.query(query).result())
    if result:
        row = result[0]
        change_pct = row.change_pct or 0

        anomaly_detected = abs(change_pct) > 50
        context["ti"].xcom_push(
            key="volume_anomaly",
            value={
                "today": row.today_count,
                "yesterday": row.yesterday_count,
                "change_pct": round(change_pct, 1),
                "anomaly": anomaly_detected,
            },
        )

        if anomaly_detected:
            raise ValueError(
                f"볼륨 이상 감지! 전일 대비 {change_pct:.1f}% 변화 "
                f"(오늘: {row.today_count:,}, 어제: {row.yesterday_count:,})"
            )


check_volume = PythonOperator(
    task_id="check_volume_anomaly",
    python_callable=_check_volume_anomaly,
    dag=dag,
)


# ─── Task 4: 결과에 따른 분기 ──────────────────────────────
def _decide_alert(**context):
    """품질 검증 결과에 따라 알림 레벨 결정."""
    events_result = context["ti"].xcom_pull(
        key="events_result", task_ids="check_events_quality"
    )
    txn_result = context["ti"].xcom_pull(
        key="txn_result", task_ids="check_transactions_quality"
    )

    any_failure = (
        not (events_result or {}).get("success", True)
        or not (txn_result or {}).get("success", True)
    )

    if any_failure:
        return "send_critical_alert"
    return "send_summary"


decide = BranchPythonOperator(
    task_id="decide_alert_level",
    python_callable=_decide_alert,
    trigger_rule=TriggerRule.ALL_DONE,  # 실패해도 분기 실행
    dag=dag,
)


# ─── Task 5a: Critical Alert ───────────────────────────────
critical_alert = SlackWebhookOperator(
    task_id="send_critical_alert",
    slack_webhook_conn_id="slack_data_alert",
    message=(
        "🚨 *QuickPay 데이터 품질 검증 실패*\n"
        "• 실행 시각: {{ ts }}\n"
        "• 대상 날짜: {{ ds }}\n"
        "• <https://ge-docs.quickpay.internal|Data Docs 확인>"
    ),
    channel="#data-alert-critical",
    dag=dag,
)

# ─── Task 5b: Summary ──────────────────────────────────────
summary_alert = SlackWebhookOperator(
    task_id="send_summary",
    slack_webhook_conn_id="slack_data_alert",
    message=(
        "✅ *QuickPay 데이터 품질 검증 통과*\n"
        "• 실행 시각: {{ ts }}\n"
        "• 대상 날짜: {{ ds }}"
    ),
    channel="#data-daily-summary",
    dag=dag,
)


# ─── DAG Dependencies ──────────────────────────────────────
# 이벤트, 트랜잭션, 볼륨 검증을 병렬 실행
[check_events, check_transactions, check_volume] >> decide
decide >> [critical_alert, summary_alert]
