# ============================================
# Cloud Storage — Bucket para datos crudos (CSVs)
#
# Los CSVs se suben organizados por carpeta:
#   gs://project-dev-490218-ecommerce-raw-data/customers/
#   gs://project-dev-490218-ecommerce-raw-data/products/
#   gs://project-dev-490218-ecommerce-raw-data/orders/
#   ...
#
# Cuando un CSV se sube, Cloud Storage dispara un evento
# OBJECT_FINALIZE (evento: archivo terminó de subir) → Pub/Sub → Cloud Function → BigQuery Bronze
# ============================================

variable "project_id" {
  type = string
}

variable "region" {
  type    = string
  default = "europe-west1"
}

# ============================================
# Bucket principal — datos crudos E-commerce
# ============================================

resource "google_storage_bucket" "ecommerce_raw_data" {
  name     = "${var.project_id}-ecommerce-raw-data"
  project  = var.project_id
  location = "EU" # Misma región que BigQuery — GDPR

  # Clase de storage: STANDARD para datos que se leen frecuentemente
  # Otras opciones: NEARLINE (30 días), COLDLINE (90 días), ARCHIVE (365 días)
  storage_class = "STANDARD"

  # Versionado: mantener versiones anteriores de los archivos
  # Útil si alguien sube un CSV corrupto — puedes volver a la versión anterior
  versioning {
    enabled = true
  }

  # Lifecycle: mover archivos viejos a storage más barato automáticamente
  # Después de 30 días → NEARLINE (más barato, se lee menos)
  # Después de 90 días → COLDLINE (aún más barato)
  lifecycle_rule {
    condition {
      age = 30 # días
    }
    action {
      type          = "SetStorageClass"
      storage_class = "NEARLINE"
    }
  }

  lifecycle_rule {
    condition {
      age = 90
    }
    action {
      type          = "SetStorageClass"
      storage_class = "COLDLINE"
    }
  }

  # Prevenir borrado accidental del bucket
  # Para borrarlo: primero cambiar a false, apply, luego destroy
  force_destroy = false

  # Acceso uniforme: todos los permisos se controlan con IAM (Identity and Access Management), no con ACLs (Access Control Lists)
  # Buena práctica: ACLs (Access Control Lists) son legacy y difíciles de auditar
  uniform_bucket_level_access = true

  labels = {
    env     = "dev"
    purpose = "raw-data-ingestion"
    layer   = "bronze"
  }
}

# ============================================
# IAM — Quién puede leer/escribir en el bucket
# ============================================

# sa-functions necesita leer los CSVs para procesarlos
resource "google_storage_bucket_iam_member" "functions_read" {
  bucket = google_storage_bucket.ecommerce_raw_data.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:sa-functions@${var.project_id}.iam.gserviceaccount.com"
}

# sa-cloudrun puede subir CSVs (si la app genera exports)
resource "google_storage_bucket_iam_member" "cloudrun_write" {
  bucket = google_storage_bucket.ecommerce_raw_data.name
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:sa-cloudrun@${var.project_id}.iam.gserviceaccount.com"
}

# ============================================
# Outputs
# ============================================

output "bucket_name" {
  value = google_storage_bucket.ecommerce_raw_data.name
}

output "bucket_url" {
  value = google_storage_bucket.ecommerce_raw_data.url
}
