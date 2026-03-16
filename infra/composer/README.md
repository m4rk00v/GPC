# Módulo Terraform: Cloud Composer — Orquestación Bronze → Silver

## Qué hace este módulo

Crea un entorno de Cloud Composer (Apache Airflow managed) que ejecuta un DAG
cada 3 minutos para transformar datos de Bronze → Silver con queries MERGE.

## Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│                    Cloud Composer (Airflow)                      │
│                                                                 │
│  DAG: bronze_to_silver                                          │
│  Schedule: */3 * * * * (cada 3 minutos)                         │
│                                                                 │
│  ┌────────────┐  ┌────────────┐                                 │
│  │ customers  │  │ products   │   ← corren en paralelo          │
│  │ MERGE      │  │ MERGE      │                                 │
│  └─────┬──────┘  └─────┬──────┘                                 │
│        │               │                                        │
│        └───────┬───────┘                                        │
│                │                                                │
│         ┌──────▼──────┐                                         │
│         │   orders    │   ← espera a customers                  │
│         │   MERGE     │                                         │
│         └──────┬──────┘                                         │
│                │                                                │
│         ┌──────┴──────┐                                         │
│         │             │                                         │
│  ┌──────▼──────┐ ┌────▼───────┐                                 │
│  │ order_items │ │ payments   │   ← esperan a orders            │
│  │ MERGE       │ │ MERGE      │                                 │
│  └─────────────┘ └────────────┘                                 │
│                                                                 │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐                   │
│  │  events    │ │ inventory  │ │  reviews   │  ← paralelo       │
│  │  MERGE     │ │ MERGE      │ │  MERGE     │  (independientes) │
│  └────────────┘ └────────────┘ └────────────┘                   │
│                                                                 │
│  Total: 9 tasks                                                 │
│  SA: sa-pipeline (bigquery.admin)                               │
└─────────────────────────────────────────────────────────────────┘
         │                              │
         ▼                              ▼
┌─────────────────┐           ┌─────────────────┐
│ BigQuery Bronze │           │ BigQuery Silver  │
│ (source)        │  MERGE →  │ (target)         │
│                 │           │                  │
│ JSON crudo      │           │ Tipado, limpio   │
│ raw_data:STRING │           │ Particionado     │
│                 │           │ Clusterizado     │
└─────────────────┘           └─────────────────┘
                                      │
                                      ▼
                              ┌─────────────────┐
                              │ BigQuery Gold    │
                              │ (vistas)         │
                              │                  │
                              │ Se calculan solas│
                              │ al consultar     │
                              └─────────────────┘
```

## Archivos

| Archivo | Qué hace |
|---|---|
| `main.tf` | Crea entorno Composer + sube DAG |
| `../../composer/dags/bronze_to_silver.py` | DAG con 9 tasks MERGE |

## Paso a paso con Terraform

### Paso 1 — Habilitar API

```bash
gcloud services enable composer.googleapis.com
```

### Paso 2 — Dar permisos a sa-pipeline

```bash
# Composer worker (necesario para ejecutar el entorno)
gcloud projects add-iam-policy-binding project-dev-490218 \
  --member="serviceAccount:sa-pipeline@project-dev-490218.iam.gserviceaccount.com" \
  --role="roles/composer.worker"

# BigQuery job user (necesario para ejecutar queries)
gcloud projects add-iam-policy-binding project-dev-490218 \
  --member="serviceAccount:sa-pipeline@project-dev-490218.iam.gserviceaccount.com" \
  --role="roles/bigquery.jobUser"

# Composer admin (para que Terraform cree el entorno)
gcloud projects add-iam-policy-binding project-dev-490218 \
  --member="serviceAccount:sa-pipeline@project-dev-490218.iam.gserviceaccount.com" \
  --role="roles/composer.admin"
```

### Paso 3 — Terraform init (detectar nuevo módulo)

```bash
cd /Users/appleuser/Desktop/GPC/infra
export GOOGLE_OAUTH_ACCESS_TOKEN=$(gcloud auth print-access-token)
terraform init
```

### Paso 4 — Terraform plan (verificar qué va a crear)

```bash
terraform plan
```

Debe mostrar:
- `google_composer_environment.ecommerce` → create
- `google_storage_bucket_object.bronze_to_silver_dag` → create

### Paso 5 — Terraform apply (crear el entorno)

> **TARDA ~20-25 MINUTOS.** Composer crea un cluster GKE, un bucket, y una instancia de Airflow.

```bash
terraform apply
```

Escribe `yes`. Ve a tomar un café.

Verificar progreso desde otra terminal:
```bash
gcloud composer environments list --locations=europe-west1
```

Estado: `CREATING` → `RUNNING`

### Paso 6 — Obtener la URL de Airflow

```bash
terraform output -module=composer airflow_uri
```

O desde CLI:
```bash
gcloud composer environments describe ecommerce-composer \
  --location=europe-west1 \
  --format="value(config.airflowUri)"
```

Abrir la URL en el navegador → Dashboard de Airflow.

### Paso 7 — Verificar el DAG en Airflow

En la UI de Airflow:

1. Buscar DAG `bronze_to_silver`
2. Debe estar **activo** (toggle verde)
3. Schedule: `*/3 * * * *` (cada 3 minutos)
4. Verás las ejecuciones automáticas:

```
Run ID                    State     Duration
scheduled__2026-03-16T12:00  ✓ success  45s
scheduled__2026-03-16T12:03  ✓ success  42s
scheduled__2026-03-16T12:06  ● running  ...
```

### Paso 8 — Verificar que Silver se llenó

```bash
bq query --use_legacy_sql=false '
SELECT "customers" as tabla, COUNT(*) as filas FROM silver.customers
UNION ALL SELECT "products", COUNT(*) FROM silver.products
UNION ALL SELECT "orders", COUNT(*) FROM silver.orders
UNION ALL SELECT "order_items", COUNT(*) FROM silver.order_items
UNION ALL SELECT "payments", COUNT(*) FROM silver.payments
UNION ALL SELECT "events", COUNT(*) FROM silver.events
UNION ALL SELECT "inventory", COUNT(*) FROM silver.inventory
UNION ALL SELECT "reviews", COUNT(*) FROM silver.reviews
ORDER BY tabla
'
```

### Paso 9 — Verificar Gold (vistas)

Como Gold son vistas sobre Silver, ahora tienen datos:

```bash
bq query --use_legacy_sql=false 'SELECT * FROM gold.customer_metrics LIMIT 5'
bq query --use_legacy_sql=false 'SELECT * FROM gold.daily_revenue LIMIT 5'
bq query --use_legacy_sql=false 'SELECT * FROM gold.conversion_funnel LIMIT 5'
```

### Paso 10 — Ver logs en Airflow

En la UI de Airflow:
1. Click en DAG `bronze_to_silver`
2. Click en un run (círculo verde)
3. Click en un task → **Log** → verás el query MERGE ejecutado
4. Pestaña **Graph** → grafo de dependencias visual
5. Pestaña **Gantt** → timeline de duración por task

Desde CLI:
```bash
gcloud composer environments run ecommerce-composer \
  --location=europe-west1 \
  tasks list -- bronze_to_silver
```

### Paso 11 — Probar el flujo completo

1. Generar nuevos CSVs:
```bash
cd /Users/appleuser/Desktop/GPC/pub-sub/sample-data
python generate.py
```

2. Subir a Bronze:
```bash
gsutil cp customers.csv "gs://project-dev-490218-ecommerce-raw-data/customers/"
```

3. Esperar ~3 minutos (el DAG corre cada 3 min)

4. Verificar que Silver se actualizó:
```bash
bq query --use_legacy_sql=false 'SELECT COUNT(*) FROM silver.customers'
```

### Paso 12 — APAGAR Composer (ahorrar créditos)

> **MUY IMPORTANTE:** Composer cobra ~$10-15/día aunque no lo uses.

**Opción A — Destroy solo Composer (recomendado):**
```bash
cd /Users/appleuser/Desktop/GPC/infra
terraform destroy -target=module.composer
```

Esto borra solo Composer. BigQuery (Bronze, Silver, Gold) no se toca.

**Opción B — Comentar el módulo en Terraform:**

Comenta el contenido de `infra/composer.tf` y corre `terraform apply`.
Así puedes volver a activarlo descomentando.

**Verificar que se borró:**
```bash
gcloud composer environments list --locations=europe-west1
```

---

## Por qué MERGE y no NOT IN

| Patrón | Seguro con NULLs | Performance | Actualiza existentes |
|---|---|---|---|
| `NOT IN` (anterior) | No — si hay un NULL descarta todo | Mala a escala | No |
| `MERGE` (actual) | Sí | Buena | Sí (WHEN MATCHED → UPDATE) |

### El MERGE hace dos cosas:
1. **Si el registro NO existe en Silver** → INSERT
2. **Si ya existe** → UPDATE (actualiza campos que cambiaron)

Así si un customer cambia de dirección, Silver se actualiza automáticamente.

---

## Cron expressions

| Expression | Significa | Uso |
|---|---|---|
| `*/3 * * * *` | Cada 3 minutos | Demo (actual) |
| `0 */6 * * *` | Cada 6 horas | Producción |
| `0 2 * * *` | Todos los días a las 2am | Nightly batch |
| `0 */1 * * *` | Cada hora | Near real-time |

Para cambiar la frecuencia, editar `schedule_interval` en `bronze_to_silver.py`.

---

## Costos

| Componente | Costo aprox |
|---|---|
| Composer entorno small | ~$10-15/día |
| BigQuery queries (MERGE) | ~$0.01-0.05/ejecución |
| **Total por día** | **~$10-15** |
| **Total por mes** | **~$300-400** |

> **Para dev:** Usar Composer solo para probar, después apagar.
> Alternativa gratis: BigQuery Scheduled Queries (sin orquestación).

---

## Dependencias entre módulos

```
infra/
├── bigquery/bronze   ← debe existir primero (tablas source)
├── bigquery/silver   ← debe existir primero (tablas target)
├── pub-sub/          ← llena Bronze con CSVs
└── composer/         ← orquesta Bronze → Silver (este módulo)
        │
        │ depends_on: bigquery_bronze, bigquery_silver
        │
        └── DAG se ejecuta cada 3 min
            └── MERGE Bronze → Silver
                └── Gold se calcula solo (vistas)
```

---

## Checklist

- [ ] API de Composer habilitada
- [ ] Permisos de sa-pipeline configurados
- [ ] `terraform init` (detectar nuevo módulo)
- [ ] `terraform apply` (crear entorno — tarda ~20 min)
- [ ] Airflow UI accesible
- [ ] DAG `bronze_to_silver` visible y activo
- [ ] DAG ejecutándose cada 3 minutos
- [ ] Silver con datos (verificar conteos)
- [ ] Gold con datos (verificar vistas)
- [ ] **Composer apagado después de probar**
