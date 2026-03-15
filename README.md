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







