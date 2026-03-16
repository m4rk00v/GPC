# ============================================
# Composer — Módulo de orquestación (Airflow)
#
# Crea el entorno de Composer y sube el DAG bronze_to_silver.py
# El DAG ejecuta MERGE cada 3 minutos: Bronze → Silver
#
# IMPORTANTE: Composer cuesta ~$300/mes.
# Para apagar solo Composer sin afectar lo demás:
#   terraform destroy -target=module.composer
# ============================================

module "composer" {
  source     = "./composer"
  project_id = var.project_id
  region     = "europe-west1"

  depends_on = [
    module.bigquery_bronze,
    module.bigquery_silver,
  ]
}
