# ─── GKE Cluster ──────────────────────────────────────────────

resource "google_container_cluster" "data_platform" {
  provider = google-beta
  name     = "data-platform-${var.environment}"
  location = var.zone

  # We manage node pools separately
  remove_default_node_pool = true
  initial_node_count       = 1

  # Network configuration
  network    = google_compute_network.vpc.id
  subnetwork = google_compute_subnetwork.gke_subnet.id

  # Private cluster
  private_cluster_config {
    enable_private_nodes    = true
    enable_private_endpoint = false
    master_ipv4_cidr_block  = "172.16.0.0/28"
  }

  # IP allocation for pods and services
  ip_allocation_policy {
    cluster_secondary_range_name  = "pods"
    services_secondary_range_name = "services"
  }

  # Workload Identity (recommended over SA keys)
  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  # Cluster features
  release_channel {
    channel = "REGULAR"
  }

  # Monitoring and logging
  logging_config {
    enable_components = ["SYSTEM_COMPONENTS", "WORKLOADS"]
  }

  monitoring_config {
    enable_components = ["SYSTEM_COMPONENTS"]
    managed_prometheus {
      enabled = true
    }
  }

  # Maintenance window (KST 02:00-06:00 = UTC 17:00-21:00)
  maintenance_policy {
    recurring_window {
      start_time = "2024-01-01T17:00:00Z"
      end_time   = "2024-01-01T21:00:00Z"
      recurrence = "FREQ=WEEKLY;BYDAY=SA,SU"
    }
  }

  depends_on = [google_project_service.apis]
}

# ─── Node Pool: General Workloads ─────────────────────────────
resource "google_container_node_pool" "general" {
  name     = "general-pool"
  cluster  = google_container_cluster.data_platform.id
  location = var.zone

  initial_node_count = var.gke_node_count

  autoscaling {
    min_node_count = 1
    max_node_count = var.gke_node_count * 2
  }

  management {
    auto_repair  = true
    auto_upgrade = true
  }

  node_config {
    machine_type = var.gke_machine_type
    disk_size_gb = 100
    disk_type    = "pd-standard"

    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform",
    ]

    # Workload Identity
    workload_metadata_config {
      mode = "GKE_METADATA"
    }

    labels = {
      environment = var.environment
      node_type   = "general"
    }

    tags = ["data-platform", "gke-node"]
  }
}

# ─── Node Pool: Pipeline Workloads (spot instances for cost) ──
resource "google_container_node_pool" "pipeline" {
  name     = "pipeline-pool"
  cluster  = google_container_cluster.data_platform.id
  location = var.zone

  initial_node_count = 1

  autoscaling {
    min_node_count = 0
    max_node_count = 5
  }

  management {
    auto_repair  = true
    auto_upgrade = true
  }

  node_config {
    machine_type = "e2-standard-4"
    disk_size_gb = 50
    spot         = true  # Spot instances for cost saving

    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform",
    ]

    workload_metadata_config {
      mode = "GKE_METADATA"
    }

    labels = {
      environment = var.environment
      node_type   = "pipeline"
    }

    taint {
      key    = "workload-type"
      value  = "pipeline"
      effect = "NO_SCHEDULE"
    }

    tags = ["data-platform", "pipeline-node"]
  }
}

# ─── VPC Network ──────────────────────────────────────────────
resource "google_compute_network" "vpc" {
  name                    = "data-platform-vpc"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "gke_subnet" {
  name          = "gke-subnet"
  ip_cidr_range = "10.0.0.0/20"
  region        = var.region
  network       = google_compute_network.vpc.id

  secondary_ip_range {
    range_name    = "pods"
    ip_cidr_range = "10.4.0.0/14"
  }

  secondary_ip_range {
    range_name    = "services"
    ip_cidr_range = "10.8.0.0/20"
  }

  private_ip_google_access = true
}

# ─── Cloud NAT (for private nodes to access internet) ─────────
resource "google_compute_router" "router" {
  name    = "data-platform-router"
  region  = var.region
  network = google_compute_network.vpc.id
}

resource "google_compute_router_nat" "nat" {
  name                               = "data-platform-nat"
  router                             = google_compute_router.router.name
  region                             = var.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"

  log_config {
    enable = true
    filter = "ERRORS_ONLY"
  }
}
