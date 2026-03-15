# ============================================
# Service Accounts
# ============================================

resource "google_service_account" "sa_pipeline" {
  account_id   = "sa-pipeline"
  display_name = "Pipeline CI/CD"
}

resource "google_service_account" "sa_cloudrun" {
  account_id   = "sa-cloudrun"
  display_name = "Cloud Run App"
}

resource "google_service_account" "sa_scheduler" {
  account_id   = "sa-scheduler"
  display_name = "Scheduler"
}

resource "google_service_account" "sa_cloudsql" {
  account_id   = "sa-cloudsql"
  display_name = "Cloud SQL"
}

resource "google_service_account" "sa_storage" {
  account_id   = "sa-storage"
  display_name = "Cloud Storage"
}

resource "google_service_account" "sa_pubsub" {
  account_id   = "sa-pubsub"
  display_name = "Pub/Sub"
}

resource "google_service_account" "sa_functions" {
  account_id   = "sa-functions"
  display_name = "Cloud Functions"
}

resource "google_service_account" "sa_loadbalancer" {
  account_id   = "sa-loadbalancer"
  display_name = "Load Balancer"
}

resource "google_service_account" "sa_monitoring" {
  account_id   = "sa-monitoring"
  display_name = "Monitoring"
}

resource "google_service_account" "sa_redis" {
  account_id   = "sa-redis"
  display_name = "Redis Cache"
}

resource "google_service_account" "sa_artifact" {
  account_id   = "sa-artifact"
  display_name = "Artifact Registry"
}

resource "google_service_account" "sa_dns" {
  account_id   = "sa-dns"
  display_name = "Cloud DNS"
}

resource "google_service_account" "sa_vpc" {
  account_id   = "sa-vpc"
  display_name = "VPC Networking"
}

# ============================================
# IAM Role Bindings
# ============================================

# --- sa-pipeline ---
resource "google_project_iam_member" "pipeline_cloudbuild" {
  project = var.project_id
  role    = "roles/cloudbuild.builds.editor"
  member  = "serviceAccount:${google_service_account.sa_pipeline.email}"
}

resource "google_project_iam_member" "pipeline_storage" {
  project = var.project_id
  role    = "roles/storage.admin"
  member  = "serviceAccount:${google_service_account.sa_pipeline.email}"
}

resource "google_project_iam_member" "pipeline_run" {
  project = var.project_id
  role    = "roles/run.admin"
  member  = "serviceAccount:${google_service_account.sa_pipeline.email}"
}

resource "google_project_iam_member" "pipeline_sa_user" {
  project = var.project_id
  role    = "roles/iam.serviceAccountUser"
  member  = "serviceAccount:${google_service_account.sa_pipeline.email}"
}

# --- sa-cloudrun ---
resource "google_project_iam_member" "cloudrun_sql" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.sa_cloudrun.email}"
}

resource "google_project_iam_member" "cloudrun_secrets" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.sa_cloudrun.email}"
}

resource "google_project_iam_member" "cloudrun_logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.sa_cloudrun.email}"
}

resource "google_project_iam_member" "cloudrun_monitoring" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.sa_cloudrun.email}"
}

# --- sa-scheduler ---
resource "google_project_iam_member" "scheduler_invoker" {
  project = var.project_id
  role    = "roles/run.invoker"
  member  = "serviceAccount:${google_service_account.sa_scheduler.email}"
}

resource "google_project_iam_member" "scheduler_logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.sa_scheduler.email}"
}

# --- sa-cloudsql ---
resource "google_project_iam_member" "cloudsql_admin" {
  project = var.project_id
  role    = "roles/cloudsql.admin"
  member  = "serviceAccount:${google_service_account.sa_cloudsql.email}"
}

resource "google_project_iam_member" "cloudsql_monitoring" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.sa_cloudsql.email}"
}

# --- sa-storage ---
resource "google_project_iam_member" "storage_objects" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.sa_storage.email}"
}

resource "google_project_iam_member" "storage_logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.sa_storage.email}"
}

# --- sa-pubsub ---
resource "google_project_iam_member" "pubsub_publisher" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.sa_pubsub.email}"
}

resource "google_project_iam_member" "pubsub_subscriber" {
  project = var.project_id
  role    = "roles/pubsub.subscriber"
  member  = "serviceAccount:${google_service_account.sa_pubsub.email}"
}

resource "google_project_iam_member" "pubsub_logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.sa_pubsub.email}"
}

# --- sa-functions ---
resource "google_project_iam_member" "functions_invoker" {
  project = var.project_id
  role    = "roles/cloudfunctions.invoker"
  member  = "serviceAccount:${google_service_account.sa_functions.email}"
}

resource "google_project_iam_member" "functions_secrets" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.sa_functions.email}"
}

resource "google_project_iam_member" "functions_logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.sa_functions.email}"
}

# --- sa-loadbalancer ---
resource "google_project_iam_member" "lb_admin" {
  project = var.project_id
  role    = "roles/compute.loadBalancerAdmin"
  member  = "serviceAccount:${google_service_account.sa_loadbalancer.email}"
}

resource "google_project_iam_member" "lb_certs" {
  project = var.project_id
  role    = "roles/certificatemanager.editor"
  member  = "serviceAccount:${google_service_account.sa_loadbalancer.email}"
}

# --- sa-monitoring ---
resource "google_project_iam_member" "monitoring_logging" {
  project = var.project_id
  role    = "roles/logging.admin"
  member  = "serviceAccount:${google_service_account.sa_monitoring.email}"
}

resource "google_project_iam_member" "monitoring_admin" {
  project = var.project_id
  role    = "roles/monitoring.admin"
  member  = "serviceAccount:${google_service_account.sa_monitoring.email}"
}

resource "google_project_iam_member" "monitoring_errors" {
  project = var.project_id
  role    = "roles/errorreporting.admin"
  member  = "serviceAccount:${google_service_account.sa_monitoring.email}"
}

# --- sa-redis ---
resource "google_project_iam_member" "redis_admin" {
  project = var.project_id
  role    = "roles/redis.admin"
  member  = "serviceAccount:${google_service_account.sa_redis.email}"
}

resource "google_project_iam_member" "redis_monitoring" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.sa_redis.email}"
}

# --- sa-artifact ---
resource "google_project_iam_member" "artifact_admin" {
  project = var.project_id
  role    = "roles/artifactregistry.admin"
  member  = "serviceAccount:${google_service_account.sa_artifact.email}"
}

resource "google_project_iam_member" "artifact_storage" {
  project = var.project_id
  role    = "roles/storage.objectViewer"
  member  = "serviceAccount:${google_service_account.sa_artifact.email}"
}

# --- sa-dns ---
resource "google_project_iam_member" "dns_admin" {
  project = var.project_id
  role    = "roles/dns.admin"
  member  = "serviceAccount:${google_service_account.sa_dns.email}"
}

# --- sa-vpc ---
resource "google_project_iam_member" "vpc_network" {
  project = var.project_id
  role    = "roles/compute.networkAdmin"
  member  = "serviceAccount:${google_service_account.sa_vpc.email}"
}

resource "google_project_iam_member" "vpc_security" {
  project = var.project_id
  role    = "roles/compute.securityAdmin"
  member  = "serviceAccount:${google_service_account.sa_vpc.email}"
}
