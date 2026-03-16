# ============================================
# Cloud Composer — Orquestación Bronze → Silver
#
# Crea:
#   1. Entorno de Composer (Airflow managed)
#   2. Sube el DAG bronze_to_silver.py al bucket de DAGs
#
# El DAG ejecuta MERGE queries cada 3 minutos (demo)
# que transforman Bronze → Silver en BigQuery
#
# IMPORTANTE: Composer cuesta ~$300/mes.
# Para apagar: terraform destroy -target=module.composer
# ============================================

variable "project_id" {
  type = string
}

variable "region" {
  type    = string
  default = "europe-west1"
}

# ============================================
# Entorno de Composer (Airflow)
#
# environment_size = "small" → mínimo (ahorra costos)
# image_version → Composer 2 + Airflow 2 (más barato que v1)
# ============================================

resource "google_composer_environment" "ecommerce" {
  name    = "ecommerce-composer"
  project = var.project_id
  region  = var.region

  config {
    # Composer 2 con Airflow 2 — más eficiente y barato que v1
    software_config {
      image_version = "composer-2.9.7-airflow-2.9.3"

      # Variables de entorno disponibles en los DAGs
      env_variables = {
        GCP_PROJECT = var.project_id
      }
    }

    # Tamaño mínimo — suficiente para demo
    # small = 1 scheduler, 1 worker, 1 triggerer
    environment_size = "ENVIRONMENT_SIZE_SMALL"

    # SA (Service Account) que Airflow usa para ejecutar tasks
    # sa-pipeline tiene bigquery.admin para correr los MERGE queries
    node_config {
      service_account = "sa-pipeline@${var.project_id}.iam.gserviceaccount.com"
    }
  }

  labels = {
    env     = "dev"
    purpose = "medallion-orchestration"
  }
}

# ============================================
# Subir el DAG al bucket de Composer
#
# Composer crea un bucket automáticamente.
# Los DAGs se suben a la carpeta /dags/ de ese bucket.
# Airflow detecta archivos nuevos en ~1-2 minutos.
# ============================================

resource "google_storage_bucket_object" "bronze_to_silver_dag" {
  name   = "dags/bronze_to_silver.py"
  bucket = replace(replace(google_composer_environment.ecommerce.config[0].dag_gcs_prefix, "gs://", ""), "/dags", "")
  source = "${path.module}/../../composer/dags/bronze_to_silver.py"

  # Si el DAG cambia, se re-sube automáticamente
  depends_on = [google_composer_environment.ecommerce]
}

# ============================================
# Outputs
# ============================================

output "composer_name" {
  value = google_composer_environment.ecommerce.name
}

output "airflow_uri" {
  description = "URL de la UI de Airflow"
  value       = google_composer_environment.ecommerce.config[0].airflow_uri
}

output "dag_gcs_prefix" {
  description = "Bucket donde se suben los DAGs"
  value       = google_composer_environment.ecommerce.config[0].dag_gcs_prefix
}
