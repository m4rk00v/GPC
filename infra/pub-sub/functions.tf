# ============================================
# Cloud Function — Ingestor de CSVs a BigQuery Bronze
#
# Flujo:
#   Pub/Sub entrega mensaje → Function se activa →
#   Lee CSV de GCS → Parsea filas → Inserta en BigQuery Bronze
#
# Gen2: usa Cloud Run internamente
#   - Mejor performance que Gen1
#   - Concurrencia nativa (múltiples requests por instancia)
#   - Mejor cold start
#
# Buenas prácticas:
#   - SA (Service Account) dedicada (sa-functions) — nunca la SA por defecto
#   - max-instances=5 — no saturar BigQuery con inserts concurrentes
#   - min-instances=0 — no pagar por instancias idle (batch, no streaming)
#   - timeout=300s — CSVs grandes pueden tardar
#   - Región europe-west1 — misma que bucket y BigQuery (EU/GDPR)
# ============================================

# ============================================
# Bucket para el código fuente de la function
#
# Cloud Functions Gen2 necesita el código en un ZIP en Cloud Storage.
# Terraform sube el ZIP automáticamente.
# ============================================

resource "google_storage_bucket" "function_source" {
  name     = "${var.project_id}-function-source"
  project  = var.project_id
  location = "EU"

  uniform_bucket_level_access = true

  # Lifecycle: borrar ZIPs viejos después de 30 días
  lifecycle_rule {
    condition {
      age = 30
    }
    action {
      type = "Delete"
    }
  }

  labels = {
    env     = "dev"
    purpose = "function-deployment"
  }
}

# ============================================
# ZIP del código fuente
#
# Empaqueta pub-sub/ingestor/ (main.py + requirements.txt)
# en un archivo ZIP que se sube a Cloud Storage.
# ============================================

data "archive_file" "ingestor_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../../pub-sub/ingestor"
  output_path = "${path.module}/tmp/ingestor.zip"
}

resource "google_storage_bucket_object" "ingestor_source" {
  name   = "ingestor-${data.archive_file.ingestor_zip.output_md5}.zip"
  bucket = google_storage_bucket.function_source.name
  source = data.archive_file.ingestor_zip.output_path

  # El nombre incluye el MD5 del ZIP — si el código cambia,
  # se sube un ZIP nuevo y la function se redeploya automáticamente.
}

# ============================================
# Cloud Function Gen2 — ingest-csv
#
# Se activa cuando Pub/Sub entrega un mensaje del topic "csv-uploaded".
# Lee el CSV de Cloud Storage y lo inserta en BigQuery Bronze.
# ============================================

resource "google_cloudfunctions2_function" "ingest_csv" {
  name     = "ingest-csv"
  project  = var.project_id
  location = var.region # europe-west1 — misma región que bucket y BigQuery

  description = "Ingesta CSVs de Cloud Storage a BigQuery Bronze via Pub/Sub"

  build_config {
    runtime     = "python312"
    entry_point = "ingest_csv" # Nombre de la función en main.py

    source {
      storage_source {
        bucket = google_storage_bucket.function_source.name
        object = google_storage_bucket_object.ingestor_source.name
      }
    }
  }

  service_config {
    # Memoria: 512MB para parsear CSVs grandes
    available_memory = "512Mi"

    # Timeout: 300s (5 min) para CSVs de 100K+ filas
    timeout_seconds = 300

    # Instancias:
    #   max=5: limitar concurrencia para no saturar BigQuery
    #   min=0: no pagar por instancias idle (es batch, no streaming)
    max_instance_count = 5
    min_instance_count = 0

    # SA (Service Account) dedicada — nunca usar la SA por defecto del proyecto
    service_account_email = "sa-functions@${var.project_id}.iam.gserviceaccount.com"

    # Variables de entorno
    environment_variables = {
      GCP_PROJECT = var.project_id
    }

    # Ingress: solo tráfico interno (Pub/Sub es interno)
    # Buena práctica: no exponer functions a internet si no es necesario
    ingress_settings = "ALLOW_INTERNAL_ONLY"
  }

  # ============================================
  # Event trigger — Pub/Sub topic "csv-uploaded"
  #
  # Cada mensaje en el topic dispara una invocación de esta function.
  # Si la function falla, Pub/Sub reintenta automáticamente.
  # Después de 5 fallos → mensaje va al Dead Letter Topic.
  # ============================================
  event_trigger {
    trigger_region = var.region
    event_type     = "google.cloud.pubsub.topic.v1.messagePublished"
    pubsub_topic   = google_pubsub_topic.csv_uploaded.id

    # Retry: reintentar en caso de fallo
    retry_policy = "RETRY"

    # SA (Service Account) que Eventarc usa para invocar la function
    service_account_email = "sa-functions@${var.project_id}.iam.gserviceaccount.com"
  }

  labels = {
    env     = "dev"
    purpose = "csv-ingestion"
    layer   = "bronze"
  }
}

# ============================================
# IAM (Identity and Access Management) — sa-functions necesita permiso para ser invocada por Eventarc
# ============================================

resource "google_project_iam_member" "functions_invoker" {
  project = var.project_id
  role    = "roles/run.invoker"
  member  = "serviceAccount:sa-functions@${var.project_id}.iam.gserviceaccount.com"
}

resource "google_project_iam_member" "functions_eventarc" {
  project = var.project_id
  role    = "roles/eventarc.eventReceiver"
  member  = "serviceAccount:sa-functions@${var.project_id}.iam.gserviceaccount.com"
}

# ============================================
# Outputs
# ============================================

output "function_name" {
  value = google_cloudfunctions2_function.ingest_csv.name
}

output "function_url" {
  value = google_cloudfunctions2_function.ingest_csv.url
}
