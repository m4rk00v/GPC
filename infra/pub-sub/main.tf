# ============================================
# Módulo Pub/Sub — Ingesta de CSVs a BigQuery Bronze
#
# Este módulo crea:
#   1. Bucket de Cloud Storage (donde se suben los CSVs)
#   2. Pub/Sub topic + Dead Letter Topic
#   3. Notificación GCS → Pub/Sub (evento OBJECT_FINALIZE)
#   4. Cloud Function Gen2 (lee CSV → inserta en BigQuery Bronze)
#
# Flujo completo:
#   CSV sube a GCS → GCS notifica a Pub/Sub → Pub/Sub trigger Function →
#   Function lee CSV → Inserta en BigQuery Bronze
#
# Uso desde infra/pubsub.tf:
#   module "pubsub_ingestion" {
#     source     = "./pub-sub"
#     project_id = var.project_id
#     region     = "europe-west1"
#   }
# ============================================

# Las variables, recursos y outputs están en:
#   storage.tf   — Bucket de Cloud Storage
#   pubsub.tf    — Topics, subscriptions, notificación
#   functions.tf — Cloud Function Gen2
