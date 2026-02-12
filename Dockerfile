FROM python:3.11-slim AS base

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY src/ src/

# --- Event Collector ---
FROM base AS event-collector
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1
CMD ["uvicorn", "src.event_collector.app:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "4"]

# --- Batch Pipeline ---
FROM base AS batch-pipeline
CMD ["python", "-m", "src.pipelines.batch_pipeline"]

# --- CDC Pipeline ---
FROM base AS cdc-pipeline
CMD ["python", "-m", "src.pipelines.cdc_realtime"]

# --- GenAI Agent ---
FROM base AS genai-agent
CMD ["python", "-m", "src.genai.data_quality_agent"]
