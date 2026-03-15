output "service_accounts" {
  description = "Emails de las service accounts creadas"
  value = {
    pipeline     = google_service_account.sa_pipeline.email
    cloudrun     = google_service_account.sa_cloudrun.email
    scheduler    = google_service_account.sa_scheduler.email
    cloudsql     = google_service_account.sa_cloudsql.email
    storage      = google_service_account.sa_storage.email
    pubsub       = google_service_account.sa_pubsub.email
    functions    = google_service_account.sa_functions.email
    loadbalancer = google_service_account.sa_loadbalancer.email
    monitoring   = google_service_account.sa_monitoring.email
    redis        = google_service_account.sa_redis.email
    artifact     = google_service_account.sa_artifact.email
    dns          = google_service_account.sa_dns.email
    vpc          = google_service_account.sa_vpc.email
  }
}
