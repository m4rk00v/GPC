# Plan: Service Accounts e IAM Roles — Stack Completo GCP

## Concepto clave

Cada servicio tiene su propia "identidad" (Service Account) con **solo los permisos que necesita** — principio de menor privilegio.

## Las 13 Service Accounts del stack

### 1. `sa-pipeline` — CI/CD (Cloud Build)

**Propósito:** Construir imágenes y desplegar

| Rol | Para qué |
|---|---|
| `roles/cloudbuild.builds.editor` | Ejecutar builds |
| `roles/storage.admin` | Push de imágenes al registry |
| `roles/run.admin` | Desplegar en Cloud Run |
| `roles/iam.serviceAccountUser` | Actuar en nombre de otras SA |

### 2. `sa-cloudrun` — Aplicación en ejecución

**Propósito:** Lo que tu app puede hacer mientras corre

| Rol | Para qué |
|---|---|
| `roles/cloudsql.client` | Conectar a Cloud SQL |
| `roles/secretmanager.secretAccessor` | Leer secretos |
| `roles/logging.logWriter` | Escribir logs |
| `roles/monitoring.metricWriter` | Enviar métricas |

### 3. `sa-scheduler` — Tareas programadas

**Propósito:** Invocar endpoints en horarios definidos

| Rol | Para qué |
|---|---|
| `roles/run.invoker` | Llamar servicios de Cloud Run |
| `roles/logging.logWriter` | Escribir logs |

### 4. `sa-cloudsql` — Base de datos Cloud SQL

**Propósito:** Administrar instancias de base de datos

| Rol | Para qué |
|---|---|
| `roles/cloudsql.admin` | Administrar instancias SQL |
| `roles/monitoring.metricWriter` | Enviar métricas de BD |

### 5. `sa-storage` — Cloud Storage (Buckets)

**Propósito:** Gestionar archivos y objetos en buckets

| Rol | Para qué |
|---|---|
| `roles/storage.objectAdmin` | CRUD de objetos en buckets |
| `roles/logging.logWriter` | Escribir logs de acceso |

### 6. `sa-pubsub` — Mensajería Pub/Sub

**Propósito:** Comunicación asíncrona entre servicios

| Rol | Para qué |
|---|---|
| `roles/pubsub.publisher` | Publicar mensajes |
| `roles/pubsub.subscriber` | Consumir mensajes |
| `roles/logging.logWriter` | Escribir logs |

### 7. `sa-functions` — Cloud Functions

**Propósito:** Ejecutar funciones serverless

| Rol | Para qué |
|---|---|
| `roles/cloudfunctions.invoker` | Invocar funciones |
| `roles/secretmanager.secretAccessor` | Leer secretos |
| `roles/logging.logWriter` | Escribir logs |

### 8. `sa-loadbalancer` — Load Balancer / CDN

**Propósito:** Balanceo de carga y certificados SSL

| Rol | Para qué |
|---|---|
| `roles/compute.loadBalancerAdmin` | Administrar load balancers |
| `roles/certificatemanager.editor` | Gestionar certificados SSL |

### 9. `sa-monitoring` — Logging y Monitoring

**Propósito:** Observabilidad centralizada del stack

| Rol | Para qué |
|---|---|
| `roles/logging.admin` | Administrar logs |
| `roles/monitoring.admin` | Administrar dashboards y alertas |
| `roles/errorreporting.admin` | Gestionar reportes de errores |

### 10. `sa-redis` — Memorystore (Redis)

**Propósito:** Cache en memoria

| Rol | Para qué |
|---|---|
| `roles/redis.admin` | Administrar instancias Redis |
| `roles/monitoring.metricWriter` | Enviar métricas de cache |

### 11. `sa-artifact` — Artifact Registry

**Propósito:** Almacenar imágenes Docker

| Rol | Para qué |
|---|---|
| `roles/artifactregistry.admin` | Administrar repositorios de imágenes |
| `roles/storage.objectViewer` | Leer objetos del storage |

### 12. `sa-dns` — Cloud DNS

**Propósito:** Gestionar dominios y registros DNS

| Rol | Para qué |
|---|---|
| `roles/dns.admin` | Administrar zonas y registros DNS |

### 13. `sa-vpc` — Networking / VPC

**Propósito:** Gestionar redes, firewalls y subnets

| Rol | Para qué |
|---|---|
| `roles/compute.networkAdmin` | Administrar redes y subnets |
| `roles/compute.securityAdmin` | Gestionar reglas de firewall |

---

## Comandos para crear las 13 SA

```bash
PROJECT_ID=project-dev-490218

gcloud iam service-accounts create sa-pipeline --display-name="Pipeline CI/CD"
gcloud iam service-accounts create sa-cloudrun --display-name="Cloud Run App"
gcloud iam service-accounts create sa-scheduler --display-name="Scheduler"
gcloud iam service-accounts create sa-cloudsql --display-name="Cloud SQL"
gcloud iam service-accounts create sa-storage --display-name="Cloud Storage"
gcloud iam service-accounts create sa-pubsub --display-name="Pub/Sub"
gcloud iam service-accounts create sa-functions --display-name="Cloud Functions"
gcloud iam service-accounts create sa-loadbalancer --display-name="Load Balancer"
gcloud iam service-accounts create sa-monitoring --display-name="Monitoring"
gcloud iam service-accounts create sa-redis --display-name="Redis Cache"
gcloud iam service-accounts create sa-artifact --display-name="Artifact Registry"
gcloud iam service-accounts create sa-dns --display-name="Cloud DNS"
gcloud iam service-accounts create sa-vpc --display-name="VPC Networking"
```

## Asignar roles a cada SA

```bash
PROJECT_ID=project-dev-490218

# --- sa-pipeline ---
for role in roles/cloudbuild.builds.editor roles/storage.admin roles/run.admin roles/iam.serviceAccountUser; do
  gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:sa-pipeline@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="$role"
done

# --- sa-cloudrun ---
for role in roles/cloudsql.client roles/secretmanager.secretAccessor roles/logging.logWriter roles/monitoring.metricWriter; do
  gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:sa-cloudrun@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="$role"
done

# --- sa-scheduler ---
for role in roles/run.invoker roles/logging.logWriter; do
  gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:sa-scheduler@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="$role"
done

# --- sa-cloudsql ---
for role in roles/cloudsql.admin roles/monitoring.metricWriter; do
  gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:sa-cloudsql@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="$role"
done

# --- sa-storage ---
for role in roles/storage.objectAdmin roles/logging.logWriter; do
  gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:sa-storage@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="$role"
done

# --- sa-pubsub ---
for role in roles/pubsub.publisher roles/pubsub.subscriber roles/logging.logWriter; do
  gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:sa-pubsub@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="$role"
done

# --- sa-functions ---
for role in roles/cloudfunctions.invoker roles/secretmanager.secretAccessor roles/logging.logWriter; do
  gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:sa-functions@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="$role"
done

# --- sa-loadbalancer ---
for role in roles/compute.loadBalancerAdmin roles/certificatemanager.editor; do
  gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:sa-loadbalancer@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="$role"
done

# --- sa-monitoring ---
for role in roles/logging.admin roles/monitoring.admin roles/errorreporting.admin; do
  gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:sa-monitoring@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="$role"
done

# --- sa-redis ---
for role in roles/redis.admin roles/monitoring.metricWriter; do
  gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:sa-redis@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="$role"
done

# --- sa-artifact ---
for role in roles/artifactregistry.admin roles/storage.objectViewer; do
  gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:sa-artifact@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="$role"
done

# --- sa-dns ---
for role in roles/dns.admin; do
  gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:sa-dns@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="$role"
done

# --- sa-vpc ---
for role in roles/compute.networkAdmin roles/compute.securityAdmin; do
  gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:sa-vpc@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="$role"
done
```

## Verificar

```bash
# Listar todas las service accounts
gcloud iam service-accounts list

# Ver roles de una SA específica
gcloud projects get-iam-policy $PROJECT_ID \
  --flatten="bindings[].members" \
  --filter="bindings.members:sa-pipeline@" \
  --format="table(bindings.role)"
```

## Por qué separar (lo que evitas)

| Si usas 1 SA para todo | Con 13 SA separadas |
|---|---|
| Un leak expone TODO | Un leak expone solo ese servicio |
| No sabes qué servicio hizo qué | Logs claros por identidad |
| Imposible auditar permisos | Cada SA tiene solo lo que necesita |
| Difícil cumplir compliance | Auditoría limpia por servicio |

---

# Configuración de GitHub + CI/CD

## Paso 1 — Crear el repo en GitHub

1. Ve a github.com → botón verde **"New"** (esquina superior izquierda)
2. Repository name: `GPC`
3. Selecciona **Private**
4. **NO** marques "Add a README file" (ya tienes uno local)
5. Click **"Create repository"**

## Paso 2 — Conectar tu proyecto local al repo

```bash
cd /Users/appleuser/Desktop/GPC
git remote add origin https://github.com/m4rk00v/GPC.git
git add .
git commit -m "initial commit"
git push -u origin main
```

## Paso 3 — Configurar Workload Identity Federation (conexión segura GitHub ↔ GCP)

> **Nota:** No usamos llaves JSON porque la organización tiene la política
> `iam.disableServiceAccountKeyCreation` activa. Workload Identity Federation
> es el método recomendado por Google — no hay credenciales que puedan filtrarse.

> **IMPORTANTE:** Este paso DEBE ejecutarse ANTES de hacer push al repo.
> Si no se ejecuta, el pipeline de GitHub fallará con el error:
> `failed to generate Google Cloud federated token ... The target service
> indicated by the "audience" parameters is invalid`

### Paso 3a — Crear sa-pipeline manualmente (prerrequisito)

> **Problema huevo-gallina:** El pipeline necesita `sa-pipeline` para autenticarse,
> pero `sa-pipeline` está definida en los archivos `.tf` que el pipeline ejecuta.
> Solución: crear `sa-pipeline` manualmente una sola vez. Las otras 12 SA las crea el pipeline.

```bash
# Crear sa-pipeline manualmente
gcloud iam service-accounts create sa-pipeline --display-name="Pipeline CI/CD"

# Darle permisos para crear recursos via Terraform
for role in roles/cloudbuild.builds.editor roles/storage.admin roles/run.admin roles/iam.serviceAccountUser roles/iam.serviceAccountAdmin roles/resourcemanager.projectIamAdmin roles/secretmanager.admin; do gcloud projects add-iam-policy-binding project-dev-490218 --member="serviceAccount:sa-pipeline@project-dev-490218.iam.gserviceaccount.com" --role="$role"; done
```

### Paso 3b — Crear Workload Identity Pool + Provider

Ejecutar estos comandos en tu terminal **uno por uno**:

```bash
gcloud services enable iamcredentials.googleapis.com
```

```bash
gcloud iam workload-identity-pools create "github-pool" --location="global" --display-name="GitHub Actions Pool"
```

```bash
gcloud iam workload-identity-pools providers create-oidc "github-provider" --location="global" --workload-identity-pool="github-pool" --display-name="GitHub Provider" --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" --attribute-condition="assertion.repository=='m4rk00v/GPC'" --issuer-uri="https://token.actions.githubusercontent.com"
```

### Paso 3c — Vincular sa-pipeline con GitHub

```bash
gcloud iam service-accounts add-iam-policy-binding "sa-pipeline@project-dev-490218.iam.gserviceaccount.com" --role="roles/iam.workloadIdentityUser" --member="principalSet://iam.googleapis.com/projects/436908511099/locations/global/workloadIdentityPools/github-pool/attribute.repository/m4rk00v/GPC"
```

### Verificar que se creó correctamente

```bash
# Ver el pool
gcloud iam workload-identity-pools list --location="global"

# Ver el provider
gcloud iam workload-identity-pools providers list --location="global" --workload-identity-pool="github-pool"

# Obtener el string completo del provider (debe coincidir con el secreto GCP_WORKLOAD_IDENTITY_PROVIDER en GitHub)
gcloud iam workload-identity-pools providers describe github-provider --location="global" --workload-identity-pool="github-pool" --format="value(name)"
```

### Orden correcto de ejecución

| Orden | Qué | Dónde |
|---|---|---|
| 1 | Crear Workload Identity Pool + Provider | Terminal (gcloud) |
| 2 | Crear secretos en GitHub | GitHub web |
| 3 | Push al repo | Terminal (git) |
| 4 | El pipeline corre automáticamente | GitHub Actions |

## Paso 4 — Configurar secretos en GitHub (paso a paso en la web)

1. Abre tu repo en github.com
2. Click en **Settings** (pestaña superior, la última a la derecha)
3. En el menú lateral izquierdo: **Secrets and variables** → **Actions**
4. Click botón verde **"New repository secret"**
5. Crear el primer secreto:
   - **Name:** `GCP_PROJECT_ID`
   - **Secret:** `project-dev-490218`
   - Click **"Add secret"**
6. Click **"New repository secret"** de nuevo
7. Crear el segundo secreto:
   - **Name:** `GCP_WORKLOAD_IDENTITY_PROVIDER`
   - **Secret:** `projects/436908511099/locations/global/workloadIdentityPools/github-pool/providers/github-provider`
   - Click **"Add secret"**
8. Click **"New repository secret"** de nuevo
9. Crear el tercer secreto:
   - **Name:** `GCP_SERVICE_ACCOUNT`
   - **Secret:** `sa-pipeline@project-dev-490218.iam.gserviceaccount.com`
   - Click **"Add secret"**

## Paso 5 — Habilitar GitHub Actions

1. En tu repo → **Settings** → menú lateral → **Actions** → **General**
2. En "Actions permissions" selecciona: **Allow all actions and reusable workflows**
3. En "Workflow permissions" selecciona: **Read and write permissions**
4. Click **"Save"**

## Paso 6 — Configurar branch protection (opcional pero recomendado)

1. En tu repo → **Settings** → menú lateral → **Branches**
2. Click **"Add branch protection rule"**
3. Branch name pattern: `main`
4. Marcar estas opciones:
   - [x] **Require a pull request before merging** — nadie puede pushear directo a main
   - [x] **Require approvals** (1 mínimo) — alguien debe aprobar el PR
   - [x] **Require status checks to pass before merging** — el terraform plan debe pasar
   - [x] **Require branches to be up to date before merging**
5. En "Status checks that are required", busca y agrega: `terraform`
6. Click **"Create"**

Esto garantiza que:
- Nadie aplica cambios sin revisión
- Si `terraform plan` falla, no se puede mergear
- Siempre se trabaja con PRs

## Paso 7 — Crear el workflow file

El archivo `.github/workflows/terraform.yml` debe existir en tu repo.
Se puede crear desde GitHub directamente:

1. En tu repo → click **"Add file"** → **"Create new file"**
2. En el nombre escribe: `.github/workflows/terraform.yml`
3. Pega este contenido:

```yaml
name: Terraform

on:
  push:
    branches: [main]
    paths: [infra/**]
  pull_request:
    branches: [main]
    paths: [infra/**]

jobs:
  terraform:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout código
        uses: actions/checkout@v4

      - name: Autenticar con GCP (Workload Identity Federation)
        uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: ${{ secrets.GCP_WORKLOAD_IDENTITY_PROVIDER }}
          service_account: ${{ secrets.GCP_SERVICE_ACCOUNT }}

      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v3

      - name: Terraform Init
        run: terraform init
        working-directory: infra

      - name: Terraform Plan
        run: terraform plan -no-color
        working-directory: infra

      - name: Terraform Apply
        if: github.ref == 'refs/heads/main' && github.event_name == 'push'
        run: terraform apply -auto-approve -no-color
        working-directory: infra
```

4. Click **"Commit changes"**

## Paso 8 — Verificar que funciona

1. Crea una nueva branch desde main
2. Haz un cambio en cualquier archivo `.tf`
3. Crea un **Pull Request**
4. Ve a la pestaña **"Actions"** de tu repo → verás `terraform plan` corriendo
5. Si pasa, mergea el PR
6. Ve de nuevo a **"Actions"** → verás `terraform apply` corriendo
7. Verifica en GCP que los cambios se aplicaron
