# ─── Service Accounts ─────────────────────────────────────────

# Pipeline Service Account (used by CDC, Batch, Event pipelines)
resource "google_service_account" "pipeline_sa" {
  account_id   = "data-pipeline-sa"
  display_name = "Data Pipeline Service Account"
  description  = "Service account for data pipeline workloads"
}

# Event Collector Service Account
resource "google_service_account" "event_collector_sa" {
  account_id   = "event-collector-sa"
  display_name = "Event Collector Service Account"
}

# GenAI Agent Service Account
resource "google_service_account" "genai_sa" {
  account_id   = "genai-agent-sa"
  display_name = "GenAI Agent Service Account"
  description  = "Service account for GenAI data quality agent"
}

# ─── IAM Bindings ─────────────────────────────────────────────

# Pipeline SA: BigQuery + Pub/Sub + GCS
resource "google_project_iam_member" "pipeline_bigquery" {
  for_each = toset([
    "roles/bigquery.dataEditor",
    "roles/bigquery.jobUser",
    "roles/pubsub.subscriber",
    "roles/pubsub.publisher",
    "roles/storage.objectAdmin",
    "roles/dataflow.worker",
  ])

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.pipeline_sa.email}"
}

# Event Collector SA: Pub/Sub publish only
resource "google_project_iam_member" "event_collector_pubsub" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.event_collector_sa.email}"
}

# GenAI SA: BigQuery read + Vertex AI
resource "google_project_iam_member" "genai_permissions" {
  for_each = toset([
    "roles/bigquery.dataViewer",
    "roles/bigquery.jobUser",
    "roles/aiplatform.user",
  ])

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.genai_sa.email}"
}

# ─── Workload Identity Bindings (GKE ↔ GCP SA) ──────────────

resource "google_service_account_iam_binding" "pipeline_workload_identity" {
  service_account_id = google_service_account.pipeline_sa.name
  role               = "roles/iam.workloadIdentityUser"
  members = [
    "serviceAccount:${var.project_id}.svc.id.goog[data-platform/data-platform-sa]",
  ]
}

resource "google_service_account_iam_binding" "event_collector_workload_identity" {
  service_account_id = google_service_account.event_collector_sa.name
  role               = "roles/iam.workloadIdentityUser"
  members = [
    "serviceAccount:${var.project_id}.svc.id.goog[data-platform/event-collector-sa]",
  ]
}

resource "google_service_account_iam_binding" "genai_workload_identity" {
  service_account_id = google_service_account.genai_sa.name
  role               = "roles/iam.workloadIdentityUser"
  members = [
    "serviceAccount:${var.project_id}.svc.id.goog[data-platform/genai-agent-sa]",
  ]
}
