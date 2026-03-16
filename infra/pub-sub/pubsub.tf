# ============================================
# Pub/Sub — Mensajería entre Cloud Storage y Cloud Function
#
# Flujo de eventos:
#   1. CSV se sube a Cloud Storage
#   2. Cloud Storage envía notificación OBJECT_FINALIZE al topic "csv-uploaded"
#   3. Pub/Sub entrega el mensaje a la subscription
#   4. Cloud Function (subscriber) procesa el CSV
#   5. Si falla 5 veces → mensaje va al Dead Letter Topic
#
# Conceptos:
#   - Topic: canal donde llegan los mensajes
#   - Subscription: conexión entre topic y subscriber
#   - Dead Letter Topic (DLQ — cola de mensajes muertos): donde van los mensajes que fallan repetidamente
#   - Ack (Acknowledgement): confirmación de que el mensaje fue procesado
# ============================================

# ============================================
# Topic principal — recibe eventos de Cloud Storage
# ============================================

resource "google_pubsub_topic" "csv_uploaded" {
  name    = "csv-uploaded"
  project = var.project_id

  # Retención de mensajes: 7 días
  # Si el subscriber está caído, los mensajes esperan hasta 7 días
  message_retention_duration = "604800s" # 7 días en segundos

  # Schema: no definimos schema porque el mensaje viene de GCS
  # y tiene formato propio (bucket, name, size, etc.)

  labels = {
    env     = "dev"
    purpose = "csv-ingestion"
    source  = "cloud-storage"
  }
}

# ============================================
# Dead Letter Topic — mensajes que fallaron 5+ veces
#
# Buena práctica: SIEMPRE crear un DLQ.
# Sin DLQ, los mensajes que fallan se reintentan indefinidamente
# y no te enteras del problema.
# ============================================

resource "google_pubsub_topic" "csv_uploaded_dlq" {
  name    = "csv-uploaded-dlq"
  project = var.project_id

  # Retención más larga en DLQ (Dead Letter Queue) para tener tiempo de investigar
  message_retention_duration = "604800s" # 7 días

  labels = {
    env     = "dev"
    purpose = "dead-letter-queue"
    source  = "csv-uploaded"
  }
}

# ============================================
# Subscription del DLQ — para poder leer los mensajes fallidos
#
# Uso: gcloud pubsub subscriptions pull csv-uploaded-dlq-sub --limit=10
# ============================================

resource "google_pubsub_subscription" "csv_uploaded_dlq_sub" {
  name    = "csv-uploaded-dlq-sub"
  topic   = google_pubsub_topic.csv_uploaded_dlq.id
  project = var.project_id

  # Tiempo que tiene el subscriber para hacer ACK
  ack_deadline_seconds = 60

  # Retención de mensajes en la subscription
  message_retention_duration = "604800s" # 7 días

  # Expiración: nunca (subscription permanente)
  expiration_policy {
    ttl = "" # Nunca expira
  }

  # Retry policy: backoff exponencial para reintentos
  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s" # 10 minutos máximo entre reintentos
  }

  labels = {
    env     = "dev"
    purpose = "dead-letter-monitoring"
  }
}

# ============================================
# Notificación Cloud Storage → Pub/Sub
#
# Cada vez que un archivo se TERMINA DE SUBIR al bucket,
# Cloud Storage envía un mensaje al topic "csv-uploaded"
# con los metadatos del archivo (bucket, nombre, tamaño, etc.)
#
# Solo OBJECT_FINALIZE (archivo subido) — no OBJECT_DELETE (borrado) ni OBJECT_ARCHIVE (archivado)
# para no generar ruido con archivos borrados o archivados.
# ============================================

resource "google_storage_notification" "csv_notification" {
  bucket         = google_storage_bucket.ecommerce_raw_data.name
  payload_format = "JSON_API_V1" # Metadatos completos del archivo
  topic          = google_pubsub_topic.csv_uploaded.id

  # Solo disparar cuando un archivo se termina de subir
  event_types = ["OBJECT_FINALIZE"]

  # Dependencia: el topic debe existir antes de la notificación
  depends_on = [
    google_pubsub_topic.csv_uploaded,
    google_pubsub_topic_iam_member.gcs_publish
  ]
}

# ============================================
# IAM (Identity and Access Management) — Cloud Storage necesita permiso para publicar en Pub/Sub
#
# Cuando Cloud Storage dispara la notificación, usa una SA interna
# de GCS (Google Cloud Storage) que necesita el rol pubsub.publisher en el topic.
# ============================================

# Obtener la SA (Service Account) de Cloud Storage del proyecto
data "google_storage_project_service_account" "gcs_account" {
  project = var.project_id
}

# Dar permiso a la SA (Service Account) de GCS (Google Cloud Storage) para publicar en el topic
resource "google_pubsub_topic_iam_member" "gcs_publish" {
  topic   = google_pubsub_topic.csv_uploaded.id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${data.google_storage_project_service_account.gcs_account.email_address}"
  project = var.project_id
}

# ============================================
# Outputs
# ============================================

output "topic_csv_uploaded" {
  value = google_pubsub_topic.csv_uploaded.name
}

output "topic_dlq" {
  value = google_pubsub_topic.csv_uploaded_dlq.name
}

output "notification_id" {
  value = google_storage_notification.csv_notification.notification_id
}
