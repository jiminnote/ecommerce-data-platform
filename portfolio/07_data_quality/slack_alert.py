"""
QuickPay 데이터 품질 알림 시스템

Great Expectations 검증 실패 시 Slack으로 자동 알림을 발송합니다.
- P0 (Critical): 즉시 알림 + 파이프라인 중단
- P1 (Warning): 알림만 발송 (수동 확인 필요)
- P2 (Info): Daily Summary에 포함

Why Slack?
→ 토스/핀테크 환경에서는 데이터 이슈 발생 시 빠른 대응이 핵심.
  이메일 알림은 평균 확인 시간 2시간, Slack은 5분 이내 확인 가능.
"""

import json
import logging
from datetime import datetime
from typing import Any

import requests

logger = logging.getLogger(__name__)

# ─── Configuration ──────────────────────────────────────────
SLACK_WEBHOOK_URL = "https://hooks.slack.com/services/T00000/B00000/XXXXX"  # 환경변수로 관리
SLACK_CHANNEL_CRITICAL = "#data-alert-critical"
SLACK_CHANNEL_WARNING = "#data-alert"
SLACK_CHANNEL_SUMMARY = "#data-daily-summary"

PRIORITY_CONFIG = {
    "P0": {
        "channel": SLACK_CHANNEL_CRITICAL,
        "color": "#FF0000",
        "emoji": "🚨",
        "action": "파이프라인 중단",
        "mention": "<!channel>",
    },
    "P1": {
        "channel": SLACK_CHANNEL_WARNING,
        "color": "#FFA500",
        "emoji": "⚠️",
        "action": "수동 확인 필요",
        "mention": "@data-oncall",
    },
    "P2": {
        "channel": SLACK_CHANNEL_SUMMARY,
        "color": "#36A64F",
        "emoji": "ℹ️",
        "action": "일일 리포트 포함",
        "mention": "",
    },
}


# ─── Core Alert Functions ───────────────────────────────────
def parse_validation_result(result: dict[str, Any]) -> list[dict]:
    """Great Expectations validation result를 파싱하여 실패 항목 추출."""
    failures = []

    for r in result.get("results", []):
        if not r.get("success", True):
            expectation = r.get("expectation_config", {})
            meta = expectation.get("meta", {})

            failures.append(
                {
                    "expectation_type": expectation.get("expectation_type", "unknown"),
                    "column": expectation.get("kwargs", {}).get("column", "N/A"),
                    "priority": meta.get("priority", "P2"),
                    "category": meta.get("category", "unknown"),
                    "description": meta.get("description", ""),
                    "observed_value": r.get("result", {}).get("observed_value"),
                    "element_count": r.get("result", {}).get("element_count"),
                    "unexpected_percent": r.get("result", {}).get(
                        "unexpected_percent", 0
                    ),
                }
            )

    return failures


def build_slack_message(
    suite_name: str,
    failures: list[dict],
    priority: str,
    run_date: str,
) -> dict:
    """Slack Block Kit 형식의 메시지를 생성합니다."""
    config = PRIORITY_CONFIG.get(priority, PRIORITY_CONFIG["P2"])

    # 실패 항목 요약 텍스트
    failure_lines = []
    for f in failures[:10]:  # 최대 10개까지 표시
        unexpected = f.get("unexpected_percent", 0)
        failure_lines.append(
            f"• `{f['column']}` — {f['description']} "
            f"(이상 비율: {unexpected:.1f}%)"
        )

    failure_text = "\n".join(failure_lines)
    if len(failures) > 10:
        failure_text += f"\n... 외 {len(failures) - 10}건"

    return {
        "channel": config["channel"],
        "username": "QuickPay Data Quality Bot",
        "icon_emoji": ":bar_chart:",
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{config['emoji']} [{priority}] 데이터 품질 검증 실패",
                },
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Suite:*\n{suite_name}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*실행일:*\n{run_date}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*실패 건수:*\n{len(failures)}건",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*조치:*\n{config['action']}",
                    },
                ],
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*실패 상세:*\n{failure_text}",
                },
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": (
                            f"🔗 <https://ge-docs.quickpay.internal/validations/{run_date}|"
                            f"Data Docs에서 전체 결과 확인> "
                            f"{config['mention']}"
                        ),
                    }
                ],
            },
        ],
    }


def send_slack_alert(message: dict, webhook_url: str | None = None) -> bool:
    """Slack Webhook으로 메시지 발송."""
    url = webhook_url or SLACK_WEBHOOK_URL

    try:
        response = requests.post(
            url,
            json=message,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        response.raise_for_status()
        logger.info(f"Slack 알림 발송 성공: {message.get('channel')}")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Slack 알림 발송 실패: {e}")
        return False


# ─── Great Expectations Callback ────────────────────────────
def on_validation_complete(
    validation_result: dict[str, Any],
    suite_name: str,
    webhook_url: str | None = None,
) -> dict[str, Any]:
    """
    Great Expectations Checkpoint의 action으로 등록하여 사용.
    검증 완료 후 자동으로 호출됩니다.

    Returns:
        처리 결과 (알림 발송 여부, 실패 건수, 최고 우선순위 등)
    """
    run_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 1. 실패 항목 파싱
    failures = parse_validation_result(validation_result)

    if not failures:
        logger.info(f"[{suite_name}] 모든 검증 통과 ✅")
        return {"success": True, "failures": 0, "alert_sent": False}

    # 2. 최고 우선순위 결정 (P0 > P1 > P2)
    priorities = [f["priority"] for f in failures]
    max_priority = "P0" if "P0" in priorities else ("P1" if "P1" in priorities else "P2")

    # 3. Slack 알림 발송
    message = build_slack_message(suite_name, failures, max_priority, run_date)
    alert_sent = send_slack_alert(message, webhook_url)

    # 4. P0 실패 시 파이프라인 중단 신호
    should_halt = max_priority == "P0"

    result = {
        "success": False,
        "failures": len(failures),
        "max_priority": max_priority,
        "alert_sent": alert_sent,
        "should_halt_pipeline": should_halt,
        "failure_details": failures,
    }

    if should_halt:
        logger.critical(
            f"🚨 [{suite_name}] P0 데이터 품질 실패 — 파이프라인 중단 필요! "
            f"실패 {len(failures)}건"
        )
    else:
        logger.warning(
            f"⚠️ [{suite_name}] 데이터 품질 경고 ({max_priority}) — "
            f"실패 {len(failures)}건"
        )

    return result


# ─── Daily Summary ──────────────────────────────────────────
def send_daily_summary(
    suite_results: list[dict[str, Any]],
    webhook_url: str | None = None,
) -> bool:
    """하루 동안의 데이터 품질 검증 결과를 요약 발송."""
    run_date = datetime.now().strftime("%Y-%m-%d")

    total_suites = len(suite_results)
    passed_suites = sum(1 for r in suite_results if r.get("success", False))
    failed_suites = total_suites - passed_suites
    total_failures = sum(r.get("failures", 0) for r in suite_results)

    status_emoji = "✅" if failed_suites == 0 else "⚠️"

    message = {
        "channel": SLACK_CHANNEL_SUMMARY,
        "username": "QuickPay Data Quality Bot",
        "icon_emoji": ":bar_chart:",
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"📊 [{run_date}] 데이터 품질 일일 리포트",
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*상태:*\n{status_emoji}"},
                    {"type": "mrkdwn", "text": f"*총 Suite:*\n{total_suites}개"},
                    {"type": "mrkdwn", "text": f"*통과:*\n{passed_suites}개"},
                    {"type": "mrkdwn", "text": f"*실패:*\n{failed_suites}개"},
                    {"type": "mrkdwn", "text": f"*총 실패 규칙:*\n{total_failures}건"},
                ],
            },
        ],
    }

    return send_slack_alert(message, webhook_url)


# ─── Entrypoint for CLI Testing ─────────────────────────────
if __name__ == "__main__":
    # 테스트용 mock validation result
    mock_result = {
        "success": False,
        "results": [
            {
                "success": False,
                "expectation_config": {
                    "expectation_type": "expect_column_values_to_not_be_null",
                    "kwargs": {"column": "user_id"},
                    "meta": {
                        "priority": "P0",
                        "category": "completeness",
                        "description": "유저 ID 필수 — 없으면 행동 분석 불가",
                    },
                },
                "result": {
                    "observed_value": 0.02,
                    "element_count": 1000000,
                    "unexpected_percent": 2.0,
                },
            },
            {
                "success": False,
                "expectation_config": {
                    "expectation_type": "expect_column_values_to_be_between",
                    "kwargs": {"column": "properties.amount"},
                    "meta": {
                        "priority": "P1",
                        "category": "accuracy",
                        "description": "결제 금액 음수 불가",
                    },
                },
                "result": {
                    "observed_value": -5000,
                    "unexpected_percent": 0.1,
                },
            },
        ],
    }

    result = on_validation_complete(mock_result, "quickpay_events_suite")
    print(json.dumps(result, indent=2, ensure_ascii=False))
