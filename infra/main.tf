terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# API de BigQuery habilitada manualmente con:
# gcloud services enable bigquery.googleapis.com
# No se gestiona con Terraform porque sa-pipeline no tiene permiso serviceusage.services.list
