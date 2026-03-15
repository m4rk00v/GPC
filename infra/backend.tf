terraform {
  backend "gcs" {
    bucket = "project-dev-490218-tfstate"
    prefix = "terraform/state"
  }
}
