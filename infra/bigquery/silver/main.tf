variable "project_id" {
  type = string
}

variable "dataset_id" {
  type = string
}

# ============================================
# Silver — Dataset.     
# ============================================

resource "google_bigquery_dataset" "silver" {
  dataset_id    = var.dataset_id
  project       = var.project_id
  friendly_name = "Silver - Cleaned Data"
  description   = "E-commerce cleaned data - datos validados y tipados"
  location      = "EU"

  default_table_expiration_ms = 157680000000 # 5 años

  labels = {
    layer = "silver"
    env   = "dev"
  }
}

# ============================================
# Silver — Tablas con PARTITION y CLUSTER
# ============================================

resource "google_bigquery_table" "customers" {
  dataset_id = google_bigquery_dataset.silver.dataset_id
  table_id   = "customers"
  project    = var.project_id

  clustering = ["country", "city"]

  schema = jsonencode([
    { name = "customer_id", type = "STRING", mode = "REQUIRED" },
    { name = "email", type = "STRING", mode = "NULLABLE" },
    { name = "first_name", type = "STRING", mode = "NULLABLE" },
    { name = "last_name", type = "STRING", mode = "NULLABLE" },
    { name = "phone", type = "STRING", mode = "NULLABLE" },
    { name = "country", type = "STRING", mode = "NULLABLE" },
    { name = "city", type = "STRING", mode = "NULLABLE" },
    { name = "address", type = "STRING", mode = "NULLABLE" },
    { name = "created_at", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "updated_at", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "processed_at", type = "TIMESTAMP", mode = "NULLABLE" }
  ])
}

resource "google_bigquery_table" "products" {
  dataset_id = google_bigquery_dataset.silver.dataset_id
  table_id   = "products"
  project    = var.project_id

  clustering = ["category", "subcategory"]

  schema = jsonencode([
    { name = "product_id", type = "STRING", mode = "REQUIRED" },
    { name = "name", type = "STRING", mode = "NULLABLE" },
    { name = "description", type = "STRING", mode = "NULLABLE" },
    { name = "category", type = "STRING", mode = "NULLABLE" },
    { name = "subcategory", type = "STRING", mode = "NULLABLE" },
    { name = "price", type = "FLOAT64", mode = "NULLABLE" },
    { name = "currency", type = "STRING", mode = "NULLABLE" },
    { name = "sku", type = "STRING", mode = "NULLABLE" },
    { name = "is_active", type = "BOOL", mode = "NULLABLE" },
    { name = "created_at", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "processed_at", type = "TIMESTAMP", mode = "NULLABLE" }
  ])
}

resource "google_bigquery_table" "orders" {
  dataset_id = google_bigquery_dataset.silver.dataset_id
  table_id   = "orders"
  project    = var.project_id

  time_partitioning {
    type  = "DAY"
    field = "ordered_at"
  }

  clustering = ["status", "shipping_country"]

  schema = jsonencode([
    { name = "order_id", type = "STRING", mode = "REQUIRED" },
    { name = "customer_id", type = "STRING", mode = "NULLABLE" },
    { name = "status", type = "STRING", mode = "NULLABLE" },
    { name = "total_amount", type = "FLOAT64", mode = "NULLABLE" },
    { name = "currency", type = "STRING", mode = "NULLABLE" },
    { name = "shipping_address", type = "STRING", mode = "NULLABLE" },
    { name = "shipping_city", type = "STRING", mode = "NULLABLE" },
    { name = "shipping_country", type = "STRING", mode = "NULLABLE" },
    { name = "ordered_at", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "shipped_at", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "delivered_at", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "processed_at", type = "TIMESTAMP", mode = "NULLABLE" }
  ])
}

resource "google_bigquery_table" "order_items" {
  dataset_id = google_bigquery_dataset.silver.dataset_id
  table_id   = "order_items"
  project    = var.project_id

  clustering = ["product_id"]

  schema = jsonencode([
    { name = "order_item_id", type = "STRING", mode = "REQUIRED" },
    { name = "order_id", type = "STRING", mode = "NULLABLE" },
    { name = "product_id", type = "STRING", mode = "NULLABLE" },
    { name = "quantity", type = "INT64", mode = "NULLABLE" },
    { name = "unit_price", type = "FLOAT64", mode = "NULLABLE" },
    { name = "total_price", type = "FLOAT64", mode = "NULLABLE" },
    { name = "discount", type = "FLOAT64", mode = "NULLABLE" },
    { name = "processed_at", type = "TIMESTAMP", mode = "NULLABLE" }
  ])
}

resource "google_bigquery_table" "payments" {
  dataset_id = google_bigquery_dataset.silver.dataset_id
  table_id   = "payments"
  project    = var.project_id

  time_partitioning {
    type  = "DAY"
    field = "paid_at"
  }

  clustering = ["payment_method", "status"]

  schema = jsonencode([
    { name = "payment_id", type = "STRING", mode = "REQUIRED" },
    { name = "order_id", type = "STRING", mode = "NULLABLE" },
    { name = "customer_id", type = "STRING", mode = "NULLABLE" },
    { name = "amount", type = "FLOAT64", mode = "NULLABLE" },
    { name = "currency", type = "STRING", mode = "NULLABLE" },
    { name = "payment_method", type = "STRING", mode = "NULLABLE" },
    { name = "status", type = "STRING", mode = "NULLABLE" },
    { name = "paid_at", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "processed_at", type = "TIMESTAMP", mode = "NULLABLE" }
  ])
}

resource "google_bigquery_table" "events" {
  dataset_id = google_bigquery_dataset.silver.dataset_id
  table_id   = "events"
  project    = var.project_id

  time_partitioning {
    type  = "DAY"
    field = "event_timestamp"
  }

  clustering = ["event_type", "customer_id", "device"]

  schema = jsonencode([
    { name = "event_id", type = "STRING", mode = "REQUIRED" },
    { name = "event_type", type = "STRING", mode = "NULLABLE" },
    { name = "customer_id", type = "STRING", mode = "NULLABLE" },
    { name = "session_id", type = "STRING", mode = "NULLABLE" },
    { name = "product_id", type = "STRING", mode = "NULLABLE" },
    { name = "search_query", type = "STRING", mode = "NULLABLE" },
    { name = "page_url", type = "STRING", mode = "NULLABLE" },
    { name = "device", type = "STRING", mode = "NULLABLE" },
    { name = "event_timestamp", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "processed_at", type = "TIMESTAMP", mode = "NULLABLE" }
  ])
}

resource "google_bigquery_table" "inventory" {
  dataset_id = google_bigquery_dataset.silver.dataset_id
  table_id   = "inventory"
  project    = var.project_id

  clustering = ["warehouse"]

  schema = jsonencode([
    { name = "product_id", type = "STRING", mode = "REQUIRED" },
    { name = "warehouse", type = "STRING", mode = "NULLABLE" },
    { name = "quantity_available", type = "INT64", mode = "NULLABLE" },
    { name = "quantity_reserved", type = "INT64", mode = "NULLABLE" },
    { name = "last_updated", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "processed_at", type = "TIMESTAMP", mode = "NULLABLE" }
  ])
}

resource "google_bigquery_table" "reviews" {
  dataset_id = google_bigquery_dataset.silver.dataset_id
  table_id   = "reviews"
  project    = var.project_id

  time_partitioning {
    type  = "DAY"
    field = "created_at"
  }

  clustering = ["product_id", "rating"]

  schema = jsonencode([
    { name = "review_id", type = "STRING", mode = "REQUIRED" },
    { name = "product_id", type = "STRING", mode = "NULLABLE" },
    { name = "customer_id", type = "STRING", mode = "NULLABLE" },
    { name = "rating", type = "INT64", mode = "NULLABLE" },
    { name = "title", type = "STRING", mode = "NULLABLE" },
    { name = "comment", type = "STRING", mode = "NULLABLE" },
    { name = "created_at", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "processed_at", type = "TIMESTAMP", mode = "NULLABLE" }
  ])
}

output "dataset_id" {
  value = google_bigquery_dataset.silver.dataset_id
}
