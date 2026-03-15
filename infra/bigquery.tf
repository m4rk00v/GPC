# ============================================
# BigQuery — Módulos por capa (Bronze / Silver / Gold)
# ============================================

module "bigquery_bronze" {
  source     = "./bigquery/bronze"
  project_id = var.project_id
  dataset_id = "bronze"
}

module "bigquery_silver" {
  source     = "./bigquery/silver"
  project_id = var.project_id
  dataset_id = "silver"
}

module "bigquery_gold" {
  source     = "./bigquery/gold"
  project_id = var.project_id
  dataset_id = "gold"

  depends_on = [module.bigquery_silver]
}

# ============================================
# IAM — Roles de BigQuery para las SA
# ============================================

resource "google_project_iam_member" "pipeline_bigquery" {
  project = var.project_id
  role    = "roles/bigquery.admin"
  member  = "serviceAccount:${google_service_account.sa_pipeline.email}"
}

resource "google_project_iam_member" "cloudrun_bigquery" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.sa_cloudrun.email}"
}

resource "google_project_iam_member" "functions_bigquery" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.sa_functions.email}"
}

resource "google_project_iam_member" "monitoring_bigquery" {
  project = var.project_id
  role    = "roles/bigquery.dataViewer"
  member  = "serviceAccount:${google_service_account.sa_monitoring.email}"
}
