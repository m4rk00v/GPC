# ============================================
# Secret Manager — Secretos del stack
# ============================================

resource "google_secret_manager_secret" "db_password" {
  secret_id = "db-password"

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "db_host" {
  secret_id = "db-host"

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "redis_url" {
  secret_id = "redis-url"

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "api_key" {
  secret_id = "api-key"

  replication {
    auto {}
  }
}
