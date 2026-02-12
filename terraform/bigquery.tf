# ─── BigQuery Datasets ────────────────────────────────────────

resource "google_bigquery_dataset" "raw" {
  dataset_id    = "raw"
  friendly_name = "Raw Data Layer"
  description   = "Append-only raw data from CDC and event pipelines"
  location      = var.bq_location

  default_table_expiration_ms = 7776000000 # 90 days

  labels = {
    environment = var.environment
    layer       = "raw"
    team        = "data-platform"
  }

  access {
    role          = "WRITER"
    user_by_email = google_service_account.pipeline_sa.email
  }

  access {
    role          = "READER"
    special_group = "projectReaders"
  }

  depends_on = [google_project_service.apis]
}

resource "google_bigquery_dataset" "staging" {
  dataset_id    = "staging"
  friendly_name = "Staging Data Layer"
  description   = "Cleaned, deduplicated, and validated data"
  location      = var.bq_location

  labels = {
    environment = var.environment
    layer       = "staging"
    team        = "data-platform"
  }

  access {
    role          = "WRITER"
    user_by_email = google_service_account.pipeline_sa.email
  }

  access {
    role          = "READER"
    special_group = "projectReaders"
  }
}

resource "google_bigquery_dataset" "mart" {
  dataset_id    = "mart"
  friendly_name = "Mart Data Layer"
  description   = "Business-ready aggregated tables optimized for analytics"
  location      = var.bq_location

  labels = {
    environment = var.environment
    layer       = "mart"
    team        = "data-platform"
  }

  access {
    role          = "WRITER"
    user_by_email = google_service_account.pipeline_sa.email
  }

  access {
    role          = "READER"
    special_group = "projectReaders"
  }
}

resource "google_bigquery_dataset" "monitoring" {
  dataset_id    = "monitoring"
  friendly_name = "Data Quality Monitoring"
  description   = "Data quality checks, pipeline metrics, and observability"
  location      = var.bq_location

  labels = {
    environment = var.environment
    layer       = "monitoring"
    team        = "data-platform"
  }
}

# ─── BigQuery Tables (Raw Layer) ─────────────────────────────

resource "google_bigquery_table" "user_events" {
  dataset_id = google_bigquery_dataset.raw.dataset_id
  table_id   = "user_events"

  time_partitioning {
    type  = "DAY"
    field = "event_timestamp"
  }

  clustering = ["event_type", "device_type"]

  schema = jsonencode([
    { name = "event_id", type = "STRING", mode = "REQUIRED" },
    { name = "event_type", type = "STRING", mode = "REQUIRED" },
    { name = "event_timestamp", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "user_id", type = "INT64", mode = "NULLABLE" },
    { name = "session_id", type = "STRING", mode = "REQUIRED" },
    { name = "device_type", type = "STRING", mode = "NULLABLE" },
    { name = "device_id", type = "STRING", mode = "NULLABLE" },
    { name = "app_version", type = "STRING", mode = "NULLABLE" },
    { name = "page_url", type = "STRING", mode = "NULLABLE" },
    { name = "referrer", type = "STRING", mode = "NULLABLE" },
    { name = "utm_source", type = "STRING", mode = "NULLABLE" },
    { name = "utm_medium", type = "STRING", mode = "NULLABLE" },
    { name = "utm_campaign", type = "STRING", mode = "NULLABLE" },
    { name = "properties", type = "STRING", mode = "NULLABLE" },
    { name = "ingested_at", type = "TIMESTAMP", mode = "NULLABLE" },
  ])

  labels = {
    pipeline = "event-collector"
  }
}

resource "google_bigquery_table" "data_quality_checks" {
  dataset_id = google_bigquery_dataset.monitoring.dataset_id
  table_id   = "data_quality_checks"

  time_partitioning {
    type  = "DAY"
    field = "checked_at"
  }

  schema = jsonencode([
    { name = "check_name", type = "STRING", mode = "REQUIRED" },
    { name = "table_name", type = "STRING", mode = "REQUIRED" },
    { name = "status", type = "STRING", mode = "REQUIRED" },
    { name = "metric_value", type = "FLOAT64", mode = "NULLABLE" },
    { name = "threshold", type = "FLOAT64", mode = "NULLABLE" },
    { name = "details", type = "STRING", mode = "NULLABLE" },
    { name = "checked_at", type = "TIMESTAMP", mode = "REQUIRED" },
  ])
}
