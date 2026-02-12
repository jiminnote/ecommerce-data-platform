"""
GenAI Data Quality Agent
Uses LLM to automatically detect, analyze, and explain data quality issues
in the BigQuery data warehouse.

This demonstrates AX (AI Transformation) capabilities by:
1. Automated anomaly detection with natural language explanations
2. Self-healing pipeline suggestions
3. Data quality report generation

GenAI Tool Usage:
- GitHub Copilot: Used for code generation and refactoring
- Claude: Used for designing data quality rules and SQL generation
- Gemini: Used as the runtime LLM for anomaly explanation
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

import structlog
from google.cloud import bigquery
from langchain.prompts import ChatPromptTemplate
from langchain.schema import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

logger = structlog.get_logger()


@dataclass
class DataQualityCheck:
    """Result of a single data quality check."""

    check_name: str
    table_name: str
    status: str  # PASS, WARN, FAIL
    metric_value: float | None = None
    threshold: float | None = None
    details: str = ""
    checked_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_name": self.check_name,
            "table_name": self.table_name,
            "status": self.status,
            "metric_value": self.metric_value,
            "threshold": self.threshold,
            "details": self.details,
            "checked_at": self.checked_at.isoformat(),
        }


@dataclass
class AnomalyReport:
    """GenAI-generated anomaly analysis report."""

    anomalies: list[DataQualityCheck]
    ai_analysis: str
    recommendations: list[str]
    generated_at: datetime = field(default_factory=datetime.utcnow)


class DataQualityAgent:
    """AI-powered Data Quality Agent.

    Combines rule-based checks with GenAI analysis:
    1. Run SQL-based quality checks against BigQuery
    2. Detect anomalies using statistical thresholds
    3. Use Gemini to explain anomalies in natural language
    4. Generate actionable recommendations
    """

    def __init__(
        self,
        project_id: str | None = None,
        model_name: str = "gemini-2.0-flash",
    ) -> None:
        self.project_id = project_id or os.getenv("GCP_PROJECT_ID", "local-dev")
        self.bq_client = bigquery.Client(project=self.project_id)

        # Initialize Gemini LLM via LangChain
        self.llm = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=os.getenv("GOOGLE_GENAI_API_KEY"),
            temperature=0.1,  # Low temperature for factual analysis
        )

        self.checks: list[DataQualityCheck] = []

    # ─── Rule-based Quality Checks ────────────────────────────

    def check_freshness(self, table: str, max_delay_minutes: int = 30) -> DataQualityCheck:
        """Check if data in a table is fresh (recently updated).

        Freshness SLA: data should be no more than {max_delay_minutes} old.
        """
        query = f"""
        SELECT
            TIMESTAMP_DIFF(
                CURRENT_TIMESTAMP(),
                MAX(ingested_at),
                MINUTE
            ) AS freshness_minutes
        FROM `{self.project_id}.raw.{table}`
        """
        try:
            result = list(self.bq_client.query(query).result())
            freshness = result[0].freshness_minutes if result else None

            if freshness is None:
                status = "FAIL"
                details = "No data found in table"
            elif freshness > max_delay_minutes:
                status = "FAIL"
                details = f"Data is {freshness} minutes old (SLA: {max_delay_minutes}m)"
            elif freshness > max_delay_minutes * 0.8:
                status = "WARN"
                details = f"Data freshness approaching SLA: {freshness}m / {max_delay_minutes}m"
            else:
                status = "PASS"
                details = f"Data is {freshness} minutes fresh"

            check = DataQualityCheck(
                check_name="freshness",
                table_name=table,
                status=status,
                metric_value=freshness,
                threshold=max_delay_minutes,
                details=details,
            )
        except Exception as e:
            check = DataQualityCheck(
                check_name="freshness",
                table_name=table,
                status="FAIL",
                details=f"Query failed: {str(e)}",
            )

        self.checks.append(check)
        return check

    def check_volume_anomaly(
        self,
        table: str,
        date_column: str = "event_timestamp",
        std_dev_threshold: float = 2.0,
    ) -> DataQualityCheck:
        """Detect volume anomalies using statistical analysis.

        Compares today's row count against the 14-day moving average.
        Flags if deviation exceeds {std_dev_threshold} standard deviations.
        """
        query = f"""
        WITH daily_counts AS (
            SELECT
                DATE({date_column}) AS dt,
                COUNT(*) AS row_count
            FROM `{self.project_id}.raw.{table}`
            WHERE DATE({date_column}) >= DATE_SUB(CURRENT_DATE(), INTERVAL 14 DAY)
            GROUP BY 1
        ),
        stats AS (
            SELECT
                AVG(row_count) AS avg_count,
                STDDEV(row_count) AS std_count
            FROM daily_counts
            WHERE dt < CURRENT_DATE()  -- Exclude today for baseline
        ),
        today AS (
            SELECT row_count AS today_count
            FROM daily_counts
            WHERE dt = CURRENT_DATE() - 1
        )
        SELECT
            today.today_count,
            stats.avg_count,
            stats.std_count,
            SAFE_DIVIDE(
                ABS(today.today_count - stats.avg_count),
                stats.std_count
            ) AS z_score
        FROM today, stats
        """
        try:
            result = list(self.bq_client.query(query).result())
            if not result:
                check = DataQualityCheck(
                    check_name="volume_anomaly",
                    table_name=table,
                    status="WARN",
                    details="Insufficient data for volume analysis",
                )
            else:
                row = result[0]
                z_score = row.z_score or 0

                if z_score > std_dev_threshold:
                    status = "FAIL"
                    direction = "higher" if row.today_count > row.avg_count else "lower"
                    details = (
                        f"Volume anomaly detected: {row.today_count:,.0f} rows "
                        f"({direction} than avg {row.avg_count:,.0f}, z-score: {z_score:.2f})"
                    )
                else:
                    status = "PASS"
                    details = f"Volume normal: {row.today_count:,.0f} rows (avg: {row.avg_count:,.0f})"

                check = DataQualityCheck(
                    check_name="volume_anomaly",
                    table_name=table,
                    status=status,
                    metric_value=z_score,
                    threshold=std_dev_threshold,
                    details=details,
                )
        except Exception as e:
            check = DataQualityCheck(
                check_name="volume_anomaly",
                table_name=table,
                status="FAIL",
                details=f"Query failed: {str(e)}",
            )

        self.checks.append(check)
        return check

    def check_null_rates(
        self,
        table: str,
        columns: list[str],
        max_null_rate: float = 0.05,
    ) -> list[DataQualityCheck]:
        """Check null rates for specified columns.

        Flags columns where null rate exceeds {max_null_rate} (default 5%).
        """
        checks = []
        for column in columns:
            query = f"""
            SELECT
                COUNTIF({column} IS NULL) / COUNT(*) AS null_rate,
                COUNT(*) AS total_rows
            FROM `{self.project_id}.raw.{table}`
            WHERE DATE(_PARTITIONTIME) = CURRENT_DATE() - 1
            """
            try:
                result = list(self.bq_client.query(query).result())
                null_rate = result[0].null_rate if result else None

                if null_rate is None:
                    status = "WARN"
                    details = "No data for null rate check"
                elif null_rate > max_null_rate:
                    status = "FAIL"
                    details = f"Column '{column}' null rate: {null_rate:.2%} (threshold: {max_null_rate:.2%})"
                else:
                    status = "PASS"
                    details = f"Column '{column}' null rate: {null_rate:.2%}"

                check = DataQualityCheck(
                    check_name=f"null_rate_{column}",
                    table_name=table,
                    status=status,
                    metric_value=null_rate,
                    threshold=max_null_rate,
                    details=details,
                )
            except Exception as e:
                check = DataQualityCheck(
                    check_name=f"null_rate_{column}",
                    table_name=table,
                    status="FAIL",
                    details=f"Query failed: {str(e)}",
                )

            checks.append(check)
            self.checks.append(check)

        return checks

    def check_duplicate_rate(self, table: str, key_column: str) -> DataQualityCheck:
        """Check for duplicate records based on a key column."""
        query = f"""
        SELECT
            COUNT(*) AS total_rows,
            COUNT(DISTINCT {key_column}) AS unique_keys,
            1 - SAFE_DIVIDE(COUNT(DISTINCT {key_column}), COUNT(*)) AS duplicate_rate
        FROM `{self.project_id}.raw.{table}`
        WHERE DATE(_PARTITIONTIME) = CURRENT_DATE() - 1
        """
        try:
            result = list(self.bq_client.query(query).result())
            if result:
                dup_rate = result[0].duplicate_rate or 0
                status = "FAIL" if dup_rate > 0.01 else "PASS"
                details = (
                    f"Duplicate rate: {dup_rate:.4%} "
                    f"({result[0].total_rows - result[0].unique_keys} duplicates)"
                )
            else:
                status = "WARN"
                dup_rate = None
                details = "No data for duplicate check"

            check = DataQualityCheck(
                check_name="duplicate_rate",
                table_name=table,
                status=status,
                metric_value=dup_rate,
                threshold=0.01,
                details=details,
            )
        except Exception as e:
            check = DataQualityCheck(
                check_name="duplicate_rate",
                table_name=table,
                status="FAIL",
                details=f"Query failed: {str(e)}",
            )

        self.checks.append(check)
        return check

    # ─── GenAI Analysis ───────────────────────────────────────

    async def analyze_with_genai(self) -> AnomalyReport:
        """Use Gemini to analyze quality check results and generate insights.

        This is the core AX (AI Transformation) feature:
        - Takes structured quality check results
        - Generates natural language analysis
        - Provides actionable recommendations
        """
        failed_checks = [c for c in self.checks if c.status in ("FAIL", "WARN")]

        if not failed_checks:
            return AnomalyReport(
                anomalies=[],
                ai_analysis="All data quality checks passed. No anomalies detected.",
                recommendations=["Continue monitoring with current thresholds."],
            )

        # Prepare context for the LLM
        check_summary = json.dumps(
            [c.to_dict() for c in failed_checks],
            indent=2,
            ensure_ascii=False,
        )

        prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="""You are a Senior Data Engineer at an e-commerce company
similar to Kurly (Korean grocery delivery platform).
Your role is to analyze data quality issues and provide actionable insights.

When analyzing issues:
1. Identify the root cause based on the patterns
2. Assess the business impact (customer experience, revenue, operations)
3. Provide specific, actionable recommendations
4. Prioritize fixes by severity and impact
5. Suggest preventive measures

Respond in Korean for the business context, with English for technical terms."""),
            HumanMessage(content=f"""다음 데이터 품질 체크 결과를 분석해주세요:

{check_summary}

분석 항목:
1. 이상 징후의 근본 원인 추정
2. 비즈니스 영향도 평가
3. 즉시 조치가 필요한 사항
4. 장기적 개선 방안
5. 재발 방지를 위한 모니터링 강화 포인트"""),
        ])

        response = await self.llm.ainvoke(prompt.format_messages())
        ai_analysis = response.content

        # Extract recommendations
        recommendations = self._extract_recommendations(ai_analysis)

        report = AnomalyReport(
            anomalies=failed_checks,
            ai_analysis=ai_analysis,
            recommendations=recommendations,
        )

        # Log the report
        logger.info(
            "GenAI quality report generated",
            total_checks=len(self.checks),
            failed_checks=len(failed_checks),
            recommendations_count=len(recommendations),
        )

        return report

    def _extract_recommendations(self, analysis: str) -> list[str]:
        """Extract actionable recommendations from AI analysis."""
        recommendations = []
        lines = analysis.split("\n")
        capture = False

        for line in lines:
            line = line.strip()
            if any(keyword in line.lower() for keyword in ["조치", "권장", "recommendation", "개선"]):
                capture = True
                continue
            if capture and line.startswith(("-", "•", "*", "1", "2", "3")):
                recommendations.append(line.lstrip("-•* 0123456789."))
            elif capture and not line:
                capture = False

        return recommendations if recommendations else ["전체 분석 리포트를 확인하세요."]

    # ─── Pipeline Integration ─────────────────────────────────

    def save_results_to_bigquery(self) -> None:
        """Save quality check results to BigQuery for historical tracking."""
        if not self.checks:
            return

        table_id = f"{self.project_id}.monitoring.data_quality_checks"
        rows = [check.to_dict() for check in self.checks]

        errors = self.bq_client.insert_rows_json(table_id, rows)
        if errors:
            logger.error("Failed to save quality results", errors=errors[:3])
        else:
            logger.info("Quality results saved", count=len(rows))

    async def run_full_check(self) -> AnomalyReport:
        """Run all data quality checks and generate AI analysis.

        This is the main entry point for the quality agent.
        Called by Airflow DAG or Kubernetes CronJob.
        """
        logger.info("Starting full data quality check")

        # 1. Freshness checks
        self.check_freshness("user_events", max_delay_minutes=30)
        self.check_freshness("cdc_orders", max_delay_minutes=15)

        # 2. Volume anomaly checks
        self.check_volume_anomaly("user_events")
        self.check_volume_anomaly("cdc_orders", date_column="cdc_timestamp")

        # 3. Null rate checks
        self.check_null_rates(
            "user_events",
            columns=["user_id", "session_id", "event_type"],
        )

        # 4. Duplicate checks
        self.check_duplicate_rate("user_events", key_column="event_id")

        # 5. AI analysis
        report = await self.analyze_with_genai()

        # 6. Save results
        self.save_results_to_bigquery()

        # Summary logging
        total = len(self.checks)
        passed = sum(1 for c in self.checks if c.status == "PASS")
        warnings = sum(1 for c in self.checks if c.status == "WARN")
        failed = sum(1 for c in self.checks if c.status == "FAIL")

        logger.info(
            "Quality check complete",
            total=total,
            passed=passed,
            warnings=warnings,
            failed=failed,
        )

        return report


async def main() -> None:
    """Entry point for the data quality agent."""
    agent = DataQualityAgent()
    report = await agent.run_full_check()

    print("\n" + "=" * 60)
    print("📊 DATA QUALITY REPORT")
    print("=" * 60)
    print(f"\n🤖 AI Analysis:\n{report.ai_analysis}")
    print(f"\n💡 Recommendations:")
    for i, rec in enumerate(report.recommendations, 1):
        print(f"  {i}. {rec}")
    print(f"\nGenerated at: {report.generated_at.isoformat()}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
