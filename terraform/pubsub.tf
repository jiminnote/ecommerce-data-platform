# ─── Pub/Sub Topics & Subscriptions ──────────────────────────

# User events topic (from Event Collector)
resource "google_pubsub_topic" "user_events" {
  name = "user-events"

  message_retention_duration = "86400s" # 24 hours

  labels = {
    environment = var.environment
    pipeline    = "event-collector"
  }

  depends_on = [google_project_service.apis]
}

# Dead letter topic for failed messages
resource "google_pubsub_topic" "user_events_dlq" {
  name = "user-events-dlq"

  labels = {
    environment = var.environment
    type        = "dead-letter"
  }
}

# Subscription for Beam/Dataflow pipeline
resource "google_pubsub_subscription" "user_events_beam" {
  name  = "user-events-beam-sub"
  topic = google_pubsub_topic.user_events.id

  ack_deadline_seconds       = 60
  message_retention_duration = "604800s" # 7 days
  retain_acked_messages      = false

  # Enable exactly-once delivery
  enable_exactly_once_delivery = true

  # Dead letter policy
  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.user_events_dlq.id
    max_delivery_attempts = 5
  }

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  expiration_policy {
    ttl = ""  # Never expire
  }

  labels = {
    consumer = "beam-pipeline"
  }
}

# CDC events topic (from Debezium)
resource "google_pubsub_topic" "cdc_events" {
  name = "cdc-events"

  message_retention_duration = "86400s"

  labels = {
    environment = var.environment
    pipeline    = "cdc"
  }
}

resource "google_pubsub_subscription" "cdc_events_sub" {
  name  = "cdc-events-sub"
  topic = google_pubsub_topic.cdc_events.id

  ack_deadline_seconds       = 60
  message_retention_duration = "604800s"

  enable_exactly_once_delivery = true

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.user_events_dlq.id
    max_delivery_attempts = 5
  }

  labels = {
    consumer = "cdc-pipeline"
  }
}
