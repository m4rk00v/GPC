variable "project_id" {
  type = string
}

variable "dataset_id" {
  type = string
}

# ============================================
# Bronze — Dataset
# ============================================

resource "google_bigquery_dataset" "bronze" {
  dataset_id    = var.dataset_id
  project       = var.project_id
  friendly_name = "Bronze - Raw Data"
  description   = "E-commerce raw data - datos crudos sin procesar"
  location      = "EU"

  default_table_expiration_ms = 63072000000 # 2 años (GDPR retention)

  labels = {
    layer = "bronze"
    env   = "dev"
  }
}

# ============================================
# Bronze — Tablas crudas (esquema explícito)
# ============================================

resource "google_bigquery_table" "customers_raw" {
  dataset_id = google_bigquery_dataset.bronze.dataset_id
  table_id              = "customers_raw"
  project               = var.project_id
  deletion_protection   = false

  schema = jsonencode([
    { name = "record_id", type = "STRING", mode = "REQUIRED" },
    { name = "raw_data", type = "STRING", mode = "NULLABLE" },
    { name = "source", type = "STRING", mode = "NULLABLE" },
    { name = "ingested_at", type = "TIMESTAMP", mode = "NULLABLE" }
  ])
}

resource "google_bigquery_table" "events_raw" {
  dataset_id = google_bigquery_dataset.bronze.dataset_id
  table_id              = "events_raw"
  project               = var.project_id
  deletion_protection   = false

  schema = jsonencode([
    { name = "event_id", type = "STRING", mode = "REQUIRED" },
    { name = "event_type", type = "STRING", mode = "NULLABLE" },
    { name = "raw_payload", type = "STRING", mode = "NULLABLE" },
    { name = "source", type = "STRING", mode = "NULLABLE" },
    { name = "ingested_at", type = "TIMESTAMP", mode = "NULLABLE" }
  ])
}

resource "google_bigquery_table" "orders_raw" {
  dataset_id = google_bigquery_dataset.bronze.dataset_id
  table_id              = "orders_raw"
  project               = var.project_id
  deletion_protection   = false

  schema = jsonencode([
    { name = "record_id", type = "STRING", mode = "REQUIRED" },
    { name = "raw_data", type = "STRING", mode = "NULLABLE" },
    { name = "source", type = "STRING", mode = "NULLABLE" },
    { name = "ingested_at", type = "TIMESTAMP", mode = "NULLABLE" }
  ])
}

resource "google_bigquery_table" "order_items_raw" {
  dataset_id = google_bigquery_dataset.bronze.dataset_id
  table_id              = "order_items_raw"
  project               = var.project_id
  deletion_protection   = false

  schema = jsonencode([
    { name = "record_id", type = "STRING", mode = "REQUIRED" },
    { name = "raw_data", type = "STRING", mode = "NULLABLE" },
    { name = "source", type = "STRING", mode = "NULLABLE" },
    { name = "ingested_at", type = "TIMESTAMP", mode = "NULLABLE" }
  ])
}

resource "google_bigquery_table" "payments_raw" {
  dataset_id = google_bigquery_dataset.bronze.dataset_id
  table_id              = "payments_raw"
  project               = var.project_id
  deletion_protection   = false

  schema = jsonencode([
    { name = "record_id", type = "STRING", mode = "REQUIRED" },
    { name = "raw_data", type = "STRING", mode = "NULLABLE" },
    { name = "source", type = "STRING", mode = "NULLABLE" },
    { name = "ingested_at", type = "TIMESTAMP", mode = "NULLABLE" }
  ])
}

resource "google_bigquery_table" "products_raw" {
  dataset_id = google_bigquery_dataset.bronze.dataset_id
  table_id              = "products_raw"
  project               = var.project_id
  deletion_protection   = false

  schema = jsonencode([
    { name = "record_id", type = "STRING", mode = "REQUIRED" },
    { name = "raw_data", type = "STRING", mode = "NULLABLE" },
    { name = "source", type = "STRING", mode = "NULLABLE" },
    { name = "ingested_at", type = "TIMESTAMP", mode = "NULLABLE" }
  ])
}

resource "google_bigquery_table" "inventory_raw" {
  dataset_id = google_bigquery_dataset.bronze.dataset_id
  table_id              = "inventory_raw"
  project               = var.project_id
  deletion_protection   = false

  schema = jsonencode([
    { name = "record_id", type = "STRING", mode = "REQUIRED" },
    { name = "raw_data", type = "STRING", mode = "NULLABLE" },
    { name = "source", type = "STRING", mode = "NULLABLE" },
    { name = "ingested_at", type = "TIMESTAMP", mode = "NULLABLE" }
  ])
}

resource "google_bigquery_table" "reviews_raw" {
  dataset_id = google_bigquery_dataset.bronze.dataset_id
  table_id              = "reviews_raw"
  project               = var.project_id
  deletion_protection   = false

  schema = jsonencode([
    { name = "record_id", type = "STRING", mode = "REQUIRED" },
    { name = "raw_data", type = "STRING", mode = "NULLABLE" },
    { name = "source", type = "STRING", mode = "NULLABLE" },
    { name = "ingested_at", type = "TIMESTAMP", mode = "NULLABLE" }
  ])
}

output "dataset_id" {
  value = google_bigquery_dataset.bronze.dataset_id
}
