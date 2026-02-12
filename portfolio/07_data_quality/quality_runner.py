"""
QuickPay 데이터 품질 검증 러너

Great Expectations Suite를 실행하고 결과에 따라 알림을 발송합니다.
Airflow DAG에서 PythonOperator로 호출됩니다.

실행 흐름:
1. BigQuery에서 대상 테이블 데이터 로드
2. Great Expectations Suite 실행
3. 결과 파싱 → Slack 알림
4. P0 실패 시 AirflowException 발생 → DAG 중단
"""

import logging
from datetime import datetime, timedelta

import great_expectations as gx
from great_expectations.checkpoint import Checkpoint

from portfolio.data_quality.slack_alert import on_validation_complete

logger = logging.getLogger(__name__)


def run_quality_check(
    suite_name: str,
    table_name: str,
    partition_date: str | None = None,
    **kwargs,
) -> dict:
    """
    데이터 품질 검증 실행.

    Args:
        suite_name: Great Expectations Suite 이름
        table_name: BigQuery 테이블 이름
        partition_date: 파티션 날짜 (YYYY-MM-DD). None이면 전일

    Returns:
        검증 결과 dict
    """
    if partition_date is None:
        partition_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    logger.info(
        f"데이터 품질 검증 시작: suite={suite_name}, "
        f"table={table_name}, date={partition_date}"
    )

    # 1. GE Context 로드
    context = gx.get_context()

    # 2. Batch Request 생성
    batch_request = {
        "datasource_name": "quickpay_bigquery",
        "data_connector_name": "default_inferred_data_connector",
        "data_asset_name": table_name,
        "batch_spec_passthrough": {
            "query": f"""
                SELECT *
                FROM `quickpay-data.analytics.{table_name}`
                WHERE DATE(event_timestamp) = '{partition_date}'
            """
        },
    }

    # 3. Checkpoint 실행
    checkpoint = Checkpoint(
        name=f"{suite_name}_checkpoint",
        data_context=context,
        validations=[
            {
                "batch_request": batch_request,
                "expectation_suite_name": suite_name,
            }
        ],
        action_list=[
            {
                "name": "store_validation_result",
                "action": {"class_name": "StoreValidationResultAction"},
            },
            {
                "name": "update_data_docs",
                "action": {"class_name": "UpdateDataDocsAction"},
            },
        ],
    )

    result = checkpoint.run()

    # 4. 결과 파싱 및 알림
    validation_result = result.to_json_dict()
    alert_result = on_validation_complete(validation_result, suite_name)

    # 5. P0 실패 시 Airflow에서 catch할 수 있도록 Exception
    if alert_result.get("should_halt_pipeline"):
        raise DataQualityError(
            f"P0 데이터 품질 실패: {suite_name} — "
            f"{alert_result['failures']}건 실패. 파이프라인 중단."
        )

    return alert_result


class DataQualityError(Exception):
    """데이터 품질 P0 실패 시 파이프라인 중단용 예외."""

    pass


# ─── 미리 정의된 검증 세트 ──────────────────────────────────
QUALITY_CHECKS = {
    "events": {
        "suite_name": "quickpay_events_suite",
        "table_name": "events",
        "description": "이벤트 로그 품질 검증",
    },
    "transactions": {
        "suite_name": "quickpay_transactions_suite",
        "table_name": "transactions",
        "description": "결제/송금 트랜잭션 품질 검증",
    },
}


def run_all_checks(partition_date: str | None = None) -> list[dict]:
    """모든 데이터 품질 검증을 순차 실행."""
    results = []
    for name, config in QUALITY_CHECKS.items():
        logger.info(f"▶ {config['description']} 실행 중...")
        try:
            result = run_quality_check(
                suite_name=config["suite_name"],
                table_name=config["table_name"],
                partition_date=partition_date,
            )
            results.append({"name": name, **result})
        except DataQualityError:
            results.append({"name": name, "success": False, "halted": True})
            raise  # P0는 즉시 중단
        except Exception as e:
            logger.error(f"검증 실행 중 오류: {name} — {e}")
            results.append({"name": name, "success": False, "error": str(e)})

    return results
