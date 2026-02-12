"""
GenAI SQL Optimizer
Uses LLM to analyze and optimize BigQuery SQL queries.

AX Capability Demonstration:
- Automated query analysis for performance bottlenecks
- Cost estimation and optimization suggestions
- Best practices enforcement for BigQuery
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import structlog
from google.cloud import bigquery
from langchain.prompts import ChatPromptTemplate
from langchain.schema import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

logger = structlog.get_logger()


@dataclass
class QueryOptimizationResult:
    """Result of SQL query optimization analysis."""

    original_query: str
    optimized_query: str
    analysis: str
    estimated_cost_reduction: str
    recommendations: list[str]
    bigquery_specific_tips: list[str]


class SQLOptimizer:
    """AI-powered BigQuery SQL optimizer.

    Uses Gemini to:
    1. Analyze query structure and identify inefficiencies
    2. Suggest BigQuery-specific optimizations
    3. Estimate cost impacts of changes
    4. Enforce best practices (partitioning, clustering usage)
    """

    def __init__(self, project_id: str | None = None) -> None:
        self.project_id = project_id or os.getenv("GCP_PROJECT_ID", "local-dev")
        self.bq_client = bigquery.Client(project=self.project_id)
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            google_api_key=os.getenv("GOOGLE_GENAI_API_KEY"),
            temperature=0.1,
        )

    async def analyze_query(self, query: str) -> QueryOptimizationResult:
        """Analyze a BigQuery SQL query and suggest optimizations."""

        # Get dry-run cost estimate
        cost_info = self._dry_run_query(query)

        prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="""You are a BigQuery SQL optimization expert.
Analyze the given SQL query and provide:

1. Performance Analysis:
   - Identify full table scans, missing partition pruning
   - Check for inefficient JOINs
   - Identify unnecessary subqueries

2. BigQuery-Specific Optimizations:
   - Partition filter usage (avoid scanning entire partitioned tables)
   - Clustering benefit analysis
   - Approximate aggregation functions (APPROX_COUNT_DISTINCT, etc.)
   - Materialized view suggestions
   - BI Engine acceleration candidates

3. Cost Optimization:
   - Estimate bytes processed reduction
   - Suggest column pruning (SELECT * → specific columns)
   - Recommend partition/cluster strategies

4. Provide the optimized query with comments explaining changes.

Respond in a structured format with clear sections."""),
            HumanMessage(content=f"""Analyze and optimize this BigQuery SQL query:

```sql
{query}
```

Dry-run cost info:
{cost_info}

Provide the optimized version and detailed analysis."""),
        ])

        response = await self.llm.ainvoke(prompt.format_messages())
        analysis = response.content

        # Parse the response to extract structured data
        optimized_query = self._extract_sql_block(analysis)
        recommendations = self._extract_list_items(analysis, "recommendation")
        bq_tips = self._extract_list_items(analysis, "bigquery")

        return QueryOptimizationResult(
            original_query=query,
            optimized_query=optimized_query or query,
            analysis=analysis,
            estimated_cost_reduction=cost_info,
            recommendations=recommendations,
            bigquery_specific_tips=bq_tips,
        )

    def _dry_run_query(self, query: str) -> str:
        """Run a dry-run query to estimate bytes processed."""
        try:
            job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
            query_job = self.bq_client.query(query, job_config=job_config)
            bytes_processed = query_job.total_bytes_processed
            cost_estimate = (bytes_processed / 1e12) * 6.25  # $6.25 per TB

            return (
                f"Estimated bytes: {bytes_processed:,.0f} "
                f"({bytes_processed / 1e9:.2f} GB), "
                f"Estimated cost: ${cost_estimate:.4f}"
            )
        except Exception as e:
            return f"Dry-run failed: {str(e)}"

    async def optimize_batch(self, queries: list[str]) -> list[QueryOptimizationResult]:
        """Optimize multiple SQL queries."""
        results = []
        for query in queries:
            result = await self.analyze_query(query)
            results.append(result)
            logger.info(
                "Query optimized",
                query_preview=query[:100],
                recommendations_count=len(result.recommendations),
            )
        return results

    @staticmethod
    def _extract_sql_block(text: str) -> str | None:
        """Extract SQL code block from LLM response."""
        lines = text.split("\n")
        in_sql = False
        sql_lines = []

        for line in lines:
            if line.strip().startswith("```sql"):
                in_sql = True
                continue
            elif line.strip() == "```" and in_sql:
                break
            elif in_sql:
                sql_lines.append(line)

        return "\n".join(sql_lines) if sql_lines else None

    @staticmethod
    def _extract_list_items(text: str, keyword: str) -> list[str]:
        """Extract list items near a keyword from LLM response."""
        items = []
        lines = text.split("\n")
        capture = False

        for line in lines:
            if keyword.lower() in line.lower():
                capture = True
                continue
            if capture and line.strip().startswith(("-", "•", "*", "1", "2", "3")):
                items.append(line.strip().lstrip("-•* 0123456789.").strip())
            elif capture and not line.strip():
                if items:
                    break

        return items
