# Módulo Terraform: Pub/Sub — Ingesta CSV → BigQuery Bronze

## Workflow

```
                         ┌─────────────────────────────┐
                         │     Developer / App / Cron   │
                         │                             │
                         │   gsutil cp data.csv        │
                         │   gs://bucket/customers/    │
                         └──────────────┬──────────────┘
                                        │
                         ┌──────────────▼──────────────┐
                         │      Cloud Storage          │
                         │      (storage.tf)           │
                         │                             │
                         │  Bucket:                    │
                         │  project-dev-490218-        │
                         │  ecommerce-raw-data         │
                         │                             │
                         │  Evento: OBJECT_FINALIZE    │
                         │  (archivo terminó de subir) │
                         └──────────────┬──────────────┘
                                        │
                         ┌──────────────▼──────────────┐
                         │      Notificación GCS       │
                         │      (pubsub.tf)            │
                         │                             │
                         │  google_storage_notification │
                         │  payload: JSON con           │
                         │  {bucket, name, size, type}  │
                         └──────────────┬──────────────┘
                                        │
                         ┌──────────────▼──────────────┐
                         │      Pub/Sub Topic          │
                         │      (pubsub.tf)            │
                         │                             │
                         │  Topic: csv-uploaded         │
                         │  Retención: 7 días           │
                         │                             │
                         │  Si falla 5 veces ──────┐   │
                         │                         │   │
                         └──────────────┬──────────┘   │
                                        │              │
                         ┌──────────────▼──────────┐   │
                         │   Eventarc Trigger       │   │
                         │   (functions.tf)         │   │
                         │                         │   │
                         │   event_type:            │   │
                         │   google.cloud.pubsub.   │   │
                         │   topic.v1.message       │   │
                         │   Published              │   │
                         └──────────────┬──────────┘   │
                                        │              │
                         ┌──────────────▼──────────┐   │
                         │   Cloud Function Gen2   │   │
                         │   "ingest-csv"          │   │
                         │   (functions.tf)         │   │
                         │                         │   │
                         │   1. Decodifica msg      │   │
                         │   2. Valida .csv         │   │
                         │   3. Detecta carpeta     │   │
                         │      → tabla Bronze      │   │
                         │   4. Lee CSV de GCS      │   │
                         │   5. Parsea filas → JSON │   │
                         │   6. Insert BigQuery     │   │
                         │   7. ACK a Pub/Sub       │   │
                         │                         │   │
                         │   SA: sa-functions       │   │
                         │   Memory: 512MB         │   │
                         │   Timeout: 300s          │   │
                         │   Max instances: 5       │   │
                         │   Región: europe-west1   │   │
                         └──────────────┬──────────┘   │
                                        │              │
                              ┌─────────▼─────────┐    │
                              │                   │    │
                         ┌────▼────┐         ┌────▼────▼────┐
                         │ BigQuery│         │  Dead Letter  │
                         │ Bronze  │         │  Topic (DLQ)  │
                         │         │         │  (pubsub.tf)  │
                         │ customers_raw │   │               │
                         │ products_raw  │   │ csv-uploaded- │
                         │ orders_raw    │   │ dlq           │
                         │ order_items   │   │               │
                         │ payments_raw  │   │ Subscription: │
                         │ events_raw    │   │ csv-uploaded-  │
                         │ inventory_raw │   │ dlq-sub       │
                         │ reviews_raw   │   │ Retención: 7d │
                         └───────────────┘   └───────────────┘
                              OK ✓               FALLO ✗
```

## Archivos del módulo

| Archivo | Qué crea | Recursos Terraform |
|---|---|---|
| `storage.tf` | Bucket + IAM + lifecycle | `google_storage_bucket`, `google_storage_bucket_iam_member` |
| `pubsub.tf` | Topics + DLQ + notificación | `google_pubsub_topic`, `google_pubsub_subscription`, `google_storage_notification` |
| `functions.tf` | Cloud Function + trigger + source | `google_cloudfunctions2_function`, `google_storage_bucket_object`, `archive_file` |
| `main.tf` | Descripción del módulo | Variables compartidas |

## Cómo se invoca

Desde `infra/pubsub.tf`:

```hcl
module "pubsub_ingestion" {
  source     = "./pub-sub"
  project_id = var.project_id
  region     = "europe-west1"

  depends_on = [module.bigquery_bronze]
}
```

## Variables

| Variable | Tipo | Default | Descripción |
|---|---|---|---|
| `project_id` | string | — | ID del proyecto GCP |
| `region` | string | `europe-west1` | Región para Function y Eventarc |

## Mapeo carpeta → tabla

La Cloud Function detecta la tabla Bronze por la carpeta del archivo en el bucket:

```
gs://bucket/customers/*.csv   → bronze.customers_raw
gs://bucket/products/*.csv    → bronze.products_raw
gs://bucket/orders/*.csv      → bronze.orders_raw
gs://bucket/order_items/*.csv → bronze.order_items_raw
gs://bucket/payments/*.csv    → bronze.payments_raw
gs://bucket/events/*.csv      → bronze.events_raw
gs://bucket/inventory/*.csv   → bronze.inventory_raw
gs://bucket/reviews/*.csv     → bronze.reviews_raw
```

## Configuración de eventos

| Evento | Origen | Destino | Cuándo se dispara |
|---|---|---|---|
| `OBJECT_FINALIZE` | Cloud Storage | Pub/Sub topic `csv-uploaded` | Archivo termina de subir |
| `messagePublished` | Pub/Sub | Cloud Function `ingest-csv` | Mensaje llega al topic |
| Dead Letter | Pub/Sub | Topic `csv-uploaded-dlq` | Function falla 5 veces seguidas |

## Retry y error handling

```
Mensaje llega al topic
        │
        ▼
Function intenta procesar
        │
        ├── OK → ACK → mensaje eliminado del topic
        │
        └── FALLO → Pub/Sub reintenta
                │
                ├── Intento 2 → FALLO
                ├── Intento 3 → FALLO
                ├── Intento 4 → FALLO
                └── Intento 5 → FALLO → mensaje va al DLQ
                                        │
                                        ▼
                                 csv-uploaded-dlq
                                 (retención 7 días)
                                        │
                                        ▼
                                 Revisar manualmente:
                                 gcloud pubsub subscriptions pull
                                 csv-uploaded-dlq-sub --limit=10
```

## Buenas prácticas aplicadas

| Práctica | Dónde | Por qué |
|---|---|---|
| Dead Letter Topic | `pubsub.tf` | Capturar mensajes que fallan sin perderlos |
| `OBJECT_FINALIZE` only | `pubsub.tf` | Solo archivos completos, no borrados |
| Bucket en EU | `storage.tf` | GDPR — datos de ciudadanos europeos |
| Uniform bucket access | `storage.tf` | IAM centralizado, no ACLs legacy |
| Lifecycle (NEARLINE/COLDLINE) | `storage.tf` | Reducir costos de storage automáticamente |
| Versioning | `storage.tf` | Rollback si suben CSV corrupto |
| Gen2 Function | `functions.tf` | Mejor performance y concurrencia |
| SA dedicada | `functions.tf` | Principio de menor privilegio |
| max-instances=5 | `functions.tf` | No saturar BigQuery con inserts |
| ALLOW_INTERNAL_ONLY | `functions.tf` | Function no expuesta a internet |
| Source hash en ZIP name | `functions.tf` | Redeploy automático cuando cambia el código |
| IAM a nivel de bucket | `storage.tf` | Solo sa-functions lee, solo sa-cloudrun escribe |

## Dependencias y flujo entre capas

### Qué hace cada componente

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│  CSV sube a GCS                                                     │
│       │                                                             │
│       ▼                                                             │
│  Pub/Sub → Cloud Function                                           │
│       │                                                             │
│       ▼                                                             │
│  ┌─────────┐      ┌─────────┐      ┌─────────┐                     │
│  │ BRONZE  │ ──── │ SILVER  │ ──── │  GOLD   │                     │
│  │         │      │         │      │         │                     │
│  │ Datos   │      │ Datos   │      │ Vistas  │                     │
│  │ crudos  │      │ limpios │      │ (auto)  │                     │
│  └─────────┘      └─────────┘      └─────────┘                     │
│       ▲                ▲                ▲                           │
│       │                │                │                           │
│  Cloud Function   Cloud Composer    Se calculan                     │
│  (este módulo)    (Airflow)         solas al                        │
│  ✓ LISTO          ✗ PENDIENTE       consultar                       │
│                                     (depende de                     │
│                                      Silver)                        │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Quién llena cada capa

| Capa | Quién la llena | Cómo | Estado |
|---|---|---|---|
| **Bronze** | Cloud Function `ingest-csv` | CSV sube a GCS → Pub/Sub → Function inserta JSON crudo | Listo |
| **Silver** | Cloud Composer (Airflow) | Query SQL programado: parsea JSON de Bronze, limpia, deduplica | Pendiente |
| **Gold** | Nadie — son vistas | Se calculan automáticamente al hacer SELECT sobre Gold | Listo (pero vacío hasta que Silver tenga datos) |

### Por qué Silver no se llena automáticamente

La Function **solo** escribe en Bronze (JSON crudo). La transformación a Silver requiere:
- Parsear JSON (`JSON_VALUE`)
- Validar tipos (STRING → TIMESTAMP, FLOAT64, etc.)
- Deduplicar registros
- Aplicar reglas de negocio

Esto lo hace **Cloud Composer (Airflow)** con queries SQL programados.
No se pone en la Cloud Function porque:

| En la Function | En Cloud Composer |
|---|---|
| Si falla el parseo, pierdes el dato crudo | Bronze siempre tiene el dato (puedes reprocesar) |
| No puedes reprocesar sin volver a subir el CSV | Puedes re-ejecutar el job de Silver cuando quieras |
| Acoplamiento: Function hace demasiado | Separación de responsabilidades |
| Sin orquestación: no sabes si Silver se actualizó | Airflow muestra el estado de cada job |

### Orden de ejecución del pipeline completo

```
1. CSV sube a GCS                              ← manual o automático
2. GCS notifica a Pub/Sub                      ← automático (OBJECT_FINALIZE)
3. Function escribe en Bronze                  ← automático (Pub/Sub trigger)
4. Cloud Composer ejecuta Bronze → Silver      ← programado (cada X horas)
5. Gold se consulta (vistas sobre Silver)      ← on-demand (Looker, API, SQL)
```

### Dependencia entre módulos Terraform

```
bigquery/bronze (datasets + tablas)
        │
        │ depends_on
        ▼
pub-sub (bucket + topics + function) ← este módulo
        │
        │ depends_on (futuro)
        ▼
cloud-composer (DAGs de Airflow: Bronze → Silver) ← PENDIENTE

bigquery/silver (tablas destino de las transformaciones)
        │
        │ depends_on
        ▼
bigquery/gold (vistas que leen Silver)
```

### Próximo paso

Configurar **Cloud Composer (Airflow)** para orquestar las transformaciones:
- DAG `bronze_to_silver`: ejecuta queries SQL que parsean Bronze → Silver
- DAG `silver_quality_check`: valida que Silver tiene datos correctos
- Frecuencia: cada 1 hora o al detectar nuevos datos en Bronze
