output "gke_cluster_name" {
  description = "GKE cluster name"
  value       = google_container_cluster.data_platform.name
}

output "gke_cluster_endpoint" {
  description = "GKE cluster endpoint"
  value       = google_container_cluster.data_platform.endpoint
  sensitive   = true
}

output "bigquery_datasets" {
  description = "BigQuery dataset IDs"
  value = {
    raw        = google_bigquery_dataset.raw.dataset_id
    staging    = google_bigquery_dataset.staging.dataset_id
    mart       = google_bigquery_dataset.mart.dataset_id
    monitoring = google_bigquery_dataset.monitoring.dataset_id
  }
}

output "pubsub_topics" {
  description = "Pub/Sub topic names"
  value = {
    user_events = google_pubsub_topic.user_events.name
    cdc_events  = google_pubsub_topic.cdc_events.name
  }
}

output "service_accounts" {
  description = "Service account emails"
  value = {
    pipeline        = google_service_account.pipeline_sa.email
    event_collector = google_service_account.event_collector_sa.email
    genai_agent     = google_service_account.genai_sa.email
  }
}
