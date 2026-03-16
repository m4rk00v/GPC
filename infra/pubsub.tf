# ============================================
# Pub/Sub — Módulo de ingesta CSV → BigQuery Bronze
#
# Crea: bucket, topics, notificación, Cloud Function
# Depende de: BigQuery Bronze (las tablas deben existir antes)
# ============================================

module "pubsub_ingestion" {
  source     = "./pub-sub"
  project_id = var.project_id
  region     = "europe-west1"

  depends_on = [module.bigquery_bronze]
}
