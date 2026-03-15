PATR I Configuration

#instalacion de SDK  brew install --cask google-cloud-sdk 


# login

 gcloud auth login


# list projects

 gcloud projects list  


set project 

# gcloud config set project project-dev-id



# part II Habilitar las API del stack


  gcloud services enable \
    compute.googleapis.com \
    container.googleapis.com \
    cloudbuild.googleapis.com \
    run.googleapis.com \
    sqladmin.googleapis.com \
    redis.googleapis.com \
    secretmanager.googleapis.com \
    cloudresourcemanager.googleapis.com \
    iam.googleapis.com \
    logging.googleapis.com \
    monitoring.googleapis.com

  # Para ver cuáles ya tienes habilitadas:
  gcloud services list --enabled



  # explote the gpc CLI



CLI and console expploration DONE



########IAM + Secret Manager

Service Accunt (SA).  Good practice s: un SA por serviciio , si una se compromete , no se acedes a todos los servicios




-- parte final --- 

Hora 1  → Entorno GCP                (base para todo lo demás)
Hora 2  → IAM + Secret Manager       (seguridad base — sin esto nada es seguro)
Hora 3  → BigQuery Medallion         (dónde viven los datos)
Hora 4  → Pub/Sub                    (cómo entran los datos)
Hora 5  → Dataflow / Beam parte 1    (cómo se mueven los datos)
Hora 6  → Dataflow / Beam parte 2    (casos avanzados y errores)
Hora 7  → Cloud DLP                  (cómo se protegen los datos — GDPR)
Hora 8  → Cloud Run + Scheduler      (cómo se exponen y orquestan los servicios)
Hora 9  → Observabilidad             (cómo sabes que todo funciona)
Hora 10 → CI/CD + Terraform          (cómo se despliega de forma segura)







