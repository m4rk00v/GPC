variable "project_id" {
  description = "ID del proyecto GCP"
  type        = string
}

variable "region" {
  description = "Región por defecto"
  type        = string
  default     = "us-central1"
}
