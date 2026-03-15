variable "project_id" {
  type = string
}

variable "dataset_id" {
  type = string
}

# ============================================
# Gold — Dataset
# ============================================

resource "google_bigquery_dataset" "gold" {
  dataset_id    = var.dataset_id
  project       = var.project_id
  friendly_name = "Gold - Business Metrics"
  description   = "E-commerce business metrics - KPIs y dashboards (vistas)"
  location      = "EU"

  labels = {
    layer = "gold"
    env   = "dev"
  }
}

# ============================================
# Gold — Vistas (no tablas)
# ============================================

resource "google_bigquery_table" "daily_revenue" {
  dataset_id = google_bigquery_dataset.gold.dataset_id
  table_id   = "daily_revenue"
  project    = var.project_id

  view {
    query          = <<-SQL
      SELECT
        DATE(o.ordered_at) AS date,
        SUM(o.total_amount) AS total_revenue,
        COUNT(DISTINCT o.order_id) AS order_count,
        AVG(o.total_amount) AS avg_order_value,
        SUM(oi.quantity) AS items_sold,
        COUNT(DISTINCT o.customer_id) AS unique_customers,
        o.currency
      FROM `${var.project_id}.silver.orders` o
      JOIN `${var.project_id}.silver.order_items` oi ON o.order_id = oi.order_id
      WHERE o.status IN ("completed", "delivered")
      GROUP BY DATE(o.ordered_at), o.currency
    SQL
    use_legacy_sql = false
  }
}

resource "google_bigquery_table" "customer_metrics" {
  dataset_id = google_bigquery_dataset.gold.dataset_id
  table_id   = "customer_metrics"
  project    = var.project_id

  view {
    query          = <<-SQL
      SELECT
        c.customer_id,
        c.first_name,
        c.last_name,
        c.country,
        SUM(o.total_amount) AS total_spent,
        COUNT(DISTINCT o.order_id) AS order_count,
        AVG(o.total_amount) AS avg_order_value,
        MIN(o.ordered_at) AS first_order_date,
        MAX(o.ordered_at) AS last_order_date,
        DATE_DIFF(CURRENT_DATE(), DATE(MAX(o.ordered_at)), DAY) AS days_since_last_order,
        CASE
          WHEN COUNT(DISTINCT o.order_id) >= 10 THEN "VIP"
          WHEN COUNT(DISTINCT o.order_id) >= 5 THEN "Loyal"
          WHEN COUNT(DISTINCT o.order_id) >= 2 THEN "Returning"
          ELSE "New"
        END AS customer_segment
      FROM `${var.project_id}.silver.customers` c
      LEFT JOIN `${var.project_id}.silver.orders` o ON c.customer_id = o.customer_id
      WHERE o.status IN ("completed", "delivered")
      GROUP BY c.customer_id, c.first_name, c.last_name, c.country
    SQL
    use_legacy_sql = false
  }
}

resource "google_bigquery_table" "product_metrics" {
  dataset_id = google_bigquery_dataset.gold.dataset_id
  table_id   = "product_metrics"
  project    = var.project_id

  view {
    query          = <<-SQL
      SELECT
        p.product_id,
        p.name AS product_name,
        p.category,
        COALESCE(SUM(oi.total_price), 0) AS total_revenue,
        COALESCE(SUM(oi.quantity), 0) AS units_sold,
        COUNT(DISTINCT oi.order_id) AS order_count,
        AVG(r.rating) AS avg_rating,
        COUNT(DISTINCT r.review_id) AS review_count
      FROM `${var.project_id}.silver.products` p
      LEFT JOIN `${var.project_id}.silver.order_items` oi ON p.product_id = oi.product_id
      LEFT JOIN `${var.project_id}.silver.reviews` r ON p.product_id = r.product_id
      GROUP BY p.product_id, p.name, p.category
    SQL
    use_legacy_sql = false
  }
}

resource "google_bigquery_table" "conversion_funnel" {
  dataset_id = google_bigquery_dataset.gold.dataset_id
  table_id   = "conversion_funnel"
  project    = var.project_id

  view {
    query          = <<-SQL
      SELECT
        DATE(event_timestamp) AS date,
        COUNTIF(event_type = "page_view") AS page_views,
        COUNTIF(event_type = "product_view") AS product_views,
        COUNTIF(event_type = "add_to_cart") AS add_to_cart,
        COUNTIF(event_type = "checkout_start") AS checkout_started,
        COUNTIF(event_type = "purchase") AS orders_completed,
        SAFE_DIVIDE(COUNTIF(event_type = "add_to_cart"), COUNTIF(event_type = "product_view")) AS view_to_cart_rate,
        SAFE_DIVIDE(COUNTIF(event_type = "checkout_start"), COUNTIF(event_type = "add_to_cart")) AS cart_to_checkout_rate,
        SAFE_DIVIDE(COUNTIF(event_type = "purchase"), COUNTIF(event_type = "checkout_start")) AS checkout_to_purchase_rate
      FROM `${var.project_id}.silver.events`
      GROUP BY DATE(event_timestamp)
    SQL
    use_legacy_sql = false
  }
}

resource "google_bigquery_table" "monthly_kpis" {
  dataset_id = google_bigquery_dataset.gold.dataset_id
  table_id   = "monthly_kpis"
  project    = var.project_id

  view {
    query          = <<-SQL
      SELECT
        DATE_TRUNC(ordered_at, MONTH) AS month,
        SUM(total_amount) AS total_revenue,
        COUNT(DISTINCT order_id) AS order_count,
        COUNT(DISTINCT customer_id) AS active_customers,
        AVG(total_amount) AS avg_order_value
      FROM `${var.project_id}.silver.orders`
      WHERE status IN ("completed", "delivered")
      GROUP BY DATE_TRUNC(ordered_at, MONTH)
    SQL
    use_legacy_sql = false
  }
}

# ============================================
# Vistas autorizadas — permite que las vistas
# de Gold lean Silver sin dar acceso directo.
#
# Técnicamente BigQuery requiere que esto se
# configure en el dataset Silver (el protegido),
# pero lo mantenemos en el módulo Gold porque
# las vistas se definen aquí.
# ============================================

resource "google_bigquery_dataset_access" "gold_reads_silver_daily_revenue" {
  dataset_id = "silver"
  project    = var.project_id

  view {
    project_id = var.project_id
    dataset_id = google_bigquery_dataset.gold.dataset_id
    table_id   = google_bigquery_table.daily_revenue.table_id
  }
}

resource "google_bigquery_dataset_access" "gold_reads_silver_customer_metrics" {
  dataset_id = "silver"
  project    = var.project_id

  view {
    project_id = var.project_id
    dataset_id = google_bigquery_dataset.gold.dataset_id
    table_id   = google_bigquery_table.customer_metrics.table_id
  }
}

resource "google_bigquery_dataset_access" "gold_reads_silver_product_metrics" {
  dataset_id = "silver"
  project    = var.project_id

  view {
    project_id = var.project_id
    dataset_id = google_bigquery_dataset.gold.dataset_id
    table_id   = google_bigquery_table.product_metrics.table_id
  }
}

resource "google_bigquery_dataset_access" "gold_reads_silver_conversion_funnel" {
  dataset_id = "silver"
  project    = var.project_id

  view {
    project_id = var.project_id
    dataset_id = google_bigquery_dataset.gold.dataset_id
    table_id   = google_bigquery_table.conversion_funnel.table_id
  }
}

resource "google_bigquery_dataset_access" "gold_reads_silver_monthly_kpis" {
  dataset_id = "silver"
  project    = var.project_id

  view {
    project_id = var.project_id
    dataset_id = google_bigquery_dataset.gold.dataset_id
    table_id   = google_bigquery_table.monthly_kpis.table_id
  }
}

output "dataset_id" {
  value = google_bigquery_dataset.gold.dataset_id
}
