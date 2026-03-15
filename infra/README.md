# Infraestructura como Código — GCP con Terraform

## Estructura del proyecto

```
infra/
├── README.md           → este archivo
├── backend.tf          → configuración del estado remoto (GCS bucket)
├── main.tf             → provider de GCP y configuración general
├── variables.tf        → variables de entrada
├── terraform.tfvars    → valores de las variables para dev
├── iam.tf              → service accounts y asignación de roles
├── secrets.tf          → Secret Manager
└── outputs.tf          → valores de salida útiles

.github/
└── workflows/
    └── terraform.yml   → pipeline CI/CD (GitHub Actions)
```

## Prerrequisitos

1. Tener `gcloud` CLI instalado y autenticado
2. Tener Terraform instalado (`brew install terraform`)
3. Tener el proyecto GCP creado (`project-dev-490218`)
4. Tener un bucket GCS para el estado de Terraform

## Paso a paso

### Paso 1 — Instalar Terraform

```bash
brew install terraform
terraform version
```

### Paso 2 — Crear bucket para el estado remoto

```bash
gsutil mb -l us-central1 gs://project-dev-490218-tfstate
```

### Paso 3 — Autenticarte con GCP para Terraform

```bash
gcloud auth login
export GOOGLE_OAUTH_ACCESS_TOKEN=$(gcloud auth print-access-token)
```

> **Nota importante:** Si `gcloud auth application-default login` falla con
> "Access blocked: Authorization Error", usa el método de arriba.
>
> **NO uses** `export GOOGLE_CREDENTIALS=$(gcloud auth print-access-token)`
> porque `GOOGLE_CREDENTIALS` espera un JSON de service account, no un token.
> Terraform fallará con `invalid character 'y' looking for beginning of value`.
>
> | Variable | Qué espera |
> |---|---|
> | `GOOGLE_CREDENTIALS` | JSON de service account |
> | `GOOGLE_OAUTH_ACCESS_TOKEN` | Access token (texto plano) |

### Paso 4 — Inicializar Terraform

```bash
cd infra/
terraform init
```

Esto descarga el provider de GCP y conecta con el bucket de estado.

### Paso 5 — Ver qué va a crear (plan)

```bash
terraform plan
```

Muestra un resumen de lo que se va a crear, modificar o destruir. No toca nada en la nube.

### Paso 6 — Verificar

```bash
gcloud iam service-accounts list
gcloud services list --enabled
```

> **Nota:** `terraform apply` no se ejecuta localmente.
> El apply lo hace el pipeline de GitHub Actions al mergear un PR a main.

## Comandos útiles

| Comando | Qué hace |
|---|---|
| `terraform init` | Inicializa el proyecto y descarga providers |
| `terraform plan` | Muestra qué va a cambiar sin aplicar nada |
| `terraform apply` | Aplica los cambios en GCP |
| `terraform destroy` | Elimina todo lo que Terraform creó |
| `terraform fmt` | Formatea los archivos .tf |
| `terraform validate` | Valida la sintaxis de los archivos |
| `terraform state list` | Lista los recursos en el estado actual |

## Pipeline CI/CD

La configuración de GitHub (secretos, branch protection, Workload Identity Federation) está documentada en:

**`/IAM_SECRET-MANAGER/IAM.md`** → sección "Configuración de GitHub + CI/CD"

### Workflow: `.github/workflows/terraform.yml`

El pipeline se activa cuando hay cambios en `infra/**`:

| Paso | Qué hace | Cuándo |
|---|---|---|
| 1. **Checkout** | Clona el repo | Siempre |
| 2. **Auth GCP** | Se autentica con Workload Identity Federation | Siempre |
| 3. **Setup Terraform** | Instala Terraform en el runner | Siempre |
| 4. **Terraform Init** | Inicializa providers y backend | Siempre |
| 5. **Terraform Plan** | Muestra qué va a cambiar | Siempre (PR y push) |
| 6. **Terraform Apply** | Aplica los cambios en GCP | Solo en merge a main |

### Resumen visual del flujo

```
Developer                    GitHub                         GCP
────────                    ──────                         ───
Cambia .tf          →  Push a branch
                       Crea PR              →  (nada aún)
                       1. Checkout
                       2. Auth GCP          →  Workload Identity Federation
                       3. Setup Terraform
                       4. terraform init    →  Conecta con bucket tfstate
                       5. terraform plan    →  Lee estado actual (no cambia nada)
                       Revisión + Aprobación
                       Merge a main
                       1-5 (se repiten)
                       6. terraform apply   →  Crea/modifica recursos en GCP
                                               Recursos actualizados ✓
```
