# Cloud Composer (Airflow) — Orquestación Bronze → Silver

## Qué es

Cloud Composer = Apache Airflow administrado por Google.
Orquesta tareas: ejecuta queries SQL programados, con dependencias, reintentos y alertas.

| Aspecto | Cloud Composer | Análogo AWS |
|---|---|---|
| Qué es | Airflow managed | Amazon MWAA |
| Para qué | Orquestar pipelines de datos | Orquestar pipelines |
| Lenguaje | Python (DAGs) | Python (DAGs) |
| Costo | ~$300-400/mes mínimo | Similar |

> **IMPORTANTE:** Cloud Composer es caro (~$300/mes).
> Este ejemplo es para aprender. Después de probar, **apagar el entorno** para no gastar créditos.
> Para producción en dev, usar BigQuery Scheduled Queries (gratis).

---

## Paso 1 — Habilitar la API

```bash
gcloud services enable composer.googleapis.com
```

---

## Paso 2 — Crear el entorno de Composer

> **Esto tarda ~20-25 minutos.** Composer crea un cluster de GKE (Kubernetes), un bucket de DAGs,
> y una instancia de Airflow. Es el paso más lento.

```bash
gcloud composer environments create ecommerce-composer \
  --location=europe-west1 \
  --image-version=composer-2.9.7-airflow-2.9.3 \
  --environment-size=small \
  --service-account=sa-pipeline@project-dev-490218.iam.gserviceaccount.com
```

| Parámetro | Valor | Por qué |
|---|---|---|
| `--location` | `europe-west1` | Misma región que BigQuery y bucket (GDPR) |
| `--image-version` | `composer-2.9.7-airflow-2.9.3` | Composer 2 (más barato que v1) |
| `--environment-size` | `small` | Mínimo — suficiente para probar |
| `--service-account` | `sa-pipeline` | SA con permisos de BigQuery admin |

Verificar progreso:
```bash
gcloud composer environments list --locations=europe-west1
```

Estado debe cambiar de `CREATING` → `RUNNING`.

> **Si quieres ver el progreso en la consola:**
> Console → **Composer** → verás el entorno creándose.

---

## Paso 3 — Dar permisos a sa-pipeline para Composer

```bash
gcloud projects add-iam-policy-binding project-dev-490218 --member="serviceAccount:sa-pipeline@project-dev-490218.iam.gserviceaccount.com" --role="roles/composer.worker"

gcloud projects add-iam-policy-binding project-dev-490218 --member="serviceAccount:sa-pipeline@project-dev-490218.iam.gserviceaccount.com" --role="roles/bigquery.jobUser"
```

---

## Paso 4 — Obtener el bucket de DAGs

Composer crea un bucket automáticamente donde subes los DAGs (archivos Python):

```bash
gcloud composer environments describe ecommerce-composer \
  --location=europe-west1 \
  --format="value(config.dagGcsPrefix)"
```

Te dará algo como: `gs://europe-west1-ecommerce-com-XXXXX-bucket/dags`

Guarda ese valor — lo usarás para subir DAGs.

---

## Paso 5 — Crear el DAG (Bronze → Silver)

Un DAG (Directed Acyclic Graph) es un flujo de trabajo en Airflow.
Nuestro DAG ejecuta queries SQL que transforman Bronze → Silver.

Crear el archivo:

```bash
mkdir -p /Users/appleuser/Desktop/GPC/composer/dags
```

**`dags/bronze_to_silver.py`:**

```python
"""
DAG: bronze_to_silver
Orquesta la transformación de datos crudos (Bronze) a datos limpios (Silver).

Flujo:
  1. Parsea JSON de Bronze
  2. Valida tipos (STRING → TIMESTAMP, FLOAT64, etc.)
  3. Deduplica registros
  4. Inserta en Silver

Frecuencia: cada 6 horas (en producción)
Para este ejemplo: trigger manual
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.providers.google.cloud.operators.bigquery import BigQueryInsertJobOperator


# ============================================
# Configuración del DAG
# ============================================

PROJECT_ID = "project-dev-490218"

default_args = {
    "owner": "data-team",
    "depends_on_past": False,           # No depende de ejecuciones anteriores
    "email_on_failure": False,          # En producción: True + email real
    "retries": 2,                       # Reintentar 2 veces si falla
    "retry_delay": timedelta(minutes=5), # Esperar 5 min entre reintentos
}

dag = DAG(
    dag_id="bronze_to_silver",
    default_args=default_args,
    description="Transforma datos crudos de Bronze a Silver (limpia, parsea, deduplica)",
    schedule_interval=None,  # Manual — en producción: "0 */6 * * *" (cada 6 horas)
    start_date=datetime(2026, 1, 1),
    catchup=False,           # No ejecutar para fechas pasadas
    tags=["ecommerce", "medallion", "bronze-to-silver"],
)


# ============================================
# Task 1: Customers — Bronze → Silver
# ============================================

customers_bronze_to_silver = BigQueryInsertJobOperator(
    task_id="customers_bronze_to_silver",
    configuration={
        "query": {
            "query": f"""
                INSERT INTO `{PROJECT_ID}.silver.customers`
                SELECT
                    JSON_VALUE(raw_data, '$.id') AS customer_id,
                    JSON_VALUE(raw_data, '$.email') AS email,
                    JSON_VALUE(raw_data, '$.first_name') AS first_name,
                    JSON_VALUE(raw_data, '$.last_name') AS last_name,
                    JSON_VALUE(raw_data, '$.phone') AS phone,
                    JSON_VALUE(raw_data, '$.country') AS country,
                    JSON_VALUE(raw_data, '$.city') AS city,
                    JSON_VALUE(raw_data, '$.address') AS address,
                    SAFE.TIMESTAMP(JSON_VALUE(raw_data, '$.created_at')) AS created_at,
                    SAFE.TIMESTAMP(JSON_VALUE(raw_data, '$.updated_at')) AS updated_at,
                    CURRENT_TIMESTAMP() AS processed_at
                FROM `{PROJECT_ID}.bronze.customers_raw`
                WHERE JSON_VALUE(raw_data, '$.id') NOT IN (
                    SELECT customer_id FROM `{PROJECT_ID}.silver.customers`
                )
            """,
            "useLegacySql": False,
        }
    },
    location="EU",
    dag=dag,
)


# ============================================
# Task 2: Products — Bronze → Silver
# ============================================

products_bronze_to_silver = BigQueryInsertJobOperator(
    task_id="products_bronze_to_silver",
    configuration={
        "query": {
            "query": f"""
                INSERT INTO `{PROJECT_ID}.silver.products`
                SELECT
                    JSON_VALUE(raw_data, '$.id') AS product_id,
                    JSON_VALUE(raw_data, '$.name') AS name,
                    JSON_VALUE(raw_data, '$.description') AS description,
                    JSON_VALUE(raw_data, '$.category') AS category,
                    JSON_VALUE(raw_data, '$.subcategory') AS subcategory,
                    SAFE_CAST(JSON_VALUE(raw_data, '$.price') AS FLOAT64) AS price,
                    JSON_VALUE(raw_data, '$.currency') AS currency,
                    JSON_VALUE(raw_data, '$.sku') AS sku,
                    SAFE_CAST(JSON_VALUE(raw_data, '$.is_active') AS BOOL) AS is_active,
                    SAFE.TIMESTAMP(JSON_VALUE(raw_data, '$.created_at')) AS created_at,
                    CURRENT_TIMESTAMP() AS processed_at
                FROM `{PROJECT_ID}.bronze.products_raw`
                WHERE JSON_VALUE(raw_data, '$.id') NOT IN (
                    SELECT product_id FROM `{PROJECT_ID}.silver.products`
                )
            """,
            "useLegacySql": False,
        }
    },
    location="EU",
    dag=dag,
)


# ============================================
# Task 3: Orders — Bronze → Silver
# ============================================

orders_bronze_to_silver = BigQueryInsertJobOperator(
    task_id="orders_bronze_to_silver",
    configuration={
        "query": {
            "query": f"""
                INSERT INTO `{PROJECT_ID}.silver.orders`
                SELECT
                    JSON_VALUE(raw_data, '$.order_id') AS order_id,
                    JSON_VALUE(raw_data, '$.customer_id') AS customer_id,
                    JSON_VALUE(raw_data, '$.status') AS status,
                    SAFE_CAST(JSON_VALUE(raw_data, '$.total_amount') AS FLOAT64) AS total_amount,
                    JSON_VALUE(raw_data, '$.currency') AS currency,
                    JSON_VALUE(raw_data, '$.shipping_address') AS shipping_address,
                    JSON_VALUE(raw_data, '$.shipping_city') AS shipping_city,
                    JSON_VALUE(raw_data, '$.shipping_country') AS shipping_country,
                    SAFE.TIMESTAMP(JSON_VALUE(raw_data, '$.ordered_at')) AS ordered_at,
                    SAFE.TIMESTAMP(JSON_VALUE(raw_data, '$.shipped_at')) AS shipped_at,
                    SAFE.TIMESTAMP(JSON_VALUE(raw_data, '$.delivered_at')) AS delivered_at,
                    CURRENT_TIMESTAMP() AS processed_at
                FROM `{PROJECT_ID}.bronze.orders_raw`
                WHERE JSON_VALUE(raw_data, '$.order_id') NOT IN (
                    SELECT order_id FROM `{PROJECT_ID}.silver.orders`
                )
            """,
            "useLegacySql": False,
        }
    },
    location="EU",
    dag=dag,
)


# ============================================
# Task 4: Events — Bronze → Silver
# ============================================

events_bronze_to_silver = BigQueryInsertJobOperator(
    task_id="events_bronze_to_silver",
    configuration={
        "query": {
            "query": f"""
                INSERT INTO `{PROJECT_ID}.silver.events`
                SELECT
                    event_id,
                    event_type,
                    JSON_VALUE(raw_payload, '$.customer_id') AS customer_id,
                    JSON_VALUE(raw_payload, '$.session_id') AS session_id,
                    JSON_VALUE(raw_payload, '$.product_id') AS product_id,
                    JSON_VALUE(raw_payload, '$.search_query') AS search_query,
                    JSON_VALUE(raw_payload, '$.page_url') AS page_url,
                    JSON_VALUE(raw_payload, '$.device') AS device,
                    SAFE.TIMESTAMP(JSON_VALUE(raw_payload, '$.timestamp')) AS event_timestamp,
                    CURRENT_TIMESTAMP() AS processed_at
                FROM `{PROJECT_ID}.bronze.events_raw`
                WHERE event_id NOT IN (
                    SELECT event_id FROM `{PROJECT_ID}.silver.events`
                )
            """,
            "useLegacySql": False,
        }
    },
    location="EU",
    dag=dag,
)


# ============================================
# Task 5: Payments — Bronze → Silver
# ============================================

payments_bronze_to_silver = BigQueryInsertJobOperator(
    task_id="payments_bronze_to_silver",
    configuration={
        "query": {
            "query": f"""
                INSERT INTO `{PROJECT_ID}.silver.payments`
                SELECT
                    JSON_VALUE(raw_data, '$.payment_id') AS payment_id,
                    JSON_VALUE(raw_data, '$.order_id') AS order_id,
                    JSON_VALUE(raw_data, '$.customer_id') AS customer_id,
                    SAFE_CAST(JSON_VALUE(raw_data, '$.amount') AS FLOAT64) AS amount,
                    JSON_VALUE(raw_data, '$.currency') AS currency,
                    JSON_VALUE(raw_data, '$.payment_method') AS payment_method,
                    JSON_VALUE(raw_data, '$.status') AS status,
                    SAFE.TIMESTAMP(JSON_VALUE(raw_data, '$.paid_at')) AS paid_at,
                    CURRENT_TIMESTAMP() AS processed_at
                FROM `{PROJECT_ID}.bronze.payments_raw`
                WHERE JSON_VALUE(raw_data, '$.payment_id') NOT IN (
                    SELECT payment_id FROM `{PROJECT_ID}.silver.payments`
                )
            """,
            "useLegacySql": False,
        }
    },
    location="EU",
    dag=dag,
)


# ============================================
# Task 6: Order Items — Bronze → Silver
# ============================================

order_items_bronze_to_silver = BigQueryInsertJobOperator(
    task_id="order_items_bronze_to_silver",
    configuration={
        "query": {
            "query": f"""
                INSERT INTO `{PROJECT_ID}.silver.order_items`
                SELECT
                    JSON_VALUE(raw_data, '$.order_item_id') AS order_item_id,
                    JSON_VALUE(raw_data, '$.order_id') AS order_id,
                    JSON_VALUE(raw_data, '$.product_id') AS product_id,
                    SAFE_CAST(JSON_VALUE(raw_data, '$.quantity') AS INT64) AS quantity,
                    SAFE_CAST(JSON_VALUE(raw_data, '$.unit_price') AS FLOAT64) AS unit_price,
                    SAFE_CAST(JSON_VALUE(raw_data, '$.total_price') AS FLOAT64) AS total_price,
                    SAFE_CAST(JSON_VALUE(raw_data, '$.discount') AS FLOAT64) AS discount,
                    CURRENT_TIMESTAMP() AS processed_at
                FROM `{PROJECT_ID}.bronze.order_items_raw`
                WHERE JSON_VALUE(raw_data, '$.order_item_id') NOT IN (
                    SELECT order_item_id FROM `{PROJECT_ID}.silver.order_items`
                )
            """,
            "useLegacySql": False,
        }
    },
    location="EU",
    dag=dag,
)


# ============================================
# Task 7: Inventory — Bronze → Silver
# ============================================

inventory_bronze_to_silver = BigQueryInsertJobOperator(
    task_id="inventory_bronze_to_silver",
    configuration={
        "query": {
            "query": f"""
                INSERT INTO `{PROJECT_ID}.silver.inventory`
                SELECT
                    JSON_VALUE(raw_data, '$.product_id') AS product_id,
                    JSON_VALUE(raw_data, '$.warehouse') AS warehouse,
                    SAFE_CAST(JSON_VALUE(raw_data, '$.quantity_available') AS INT64) AS quantity_available,
                    SAFE_CAST(JSON_VALUE(raw_data, '$.quantity_reserved') AS INT64) AS quantity_reserved,
                    SAFE.TIMESTAMP(JSON_VALUE(raw_data, '$.last_updated')) AS last_updated,
                    CURRENT_TIMESTAMP() AS processed_at
                FROM `{PROJECT_ID}.bronze.inventory_raw`
                WHERE JSON_VALUE(raw_data, '$.product_id') NOT IN (
                    SELECT product_id FROM `{PROJECT_ID}.silver.inventory`
                )
            """,
            "useLegacySql": False,
        }
    },
    location="EU",
    dag=dag,
)


# ============================================
# Task 8: Reviews — Bronze → Silver
# ============================================

reviews_bronze_to_silver = BigQueryInsertJobOperator(
    task_id="reviews_bronze_to_silver",
    configuration={
        "query": {
            "query": f"""
                INSERT INTO `{PROJECT_ID}.silver.reviews`
                SELECT
                    JSON_VALUE(raw_data, '$.review_id') AS review_id,
                    JSON_VALUE(raw_data, '$.product_id') AS product_id,
                    JSON_VALUE(raw_data, '$.customer_id') AS customer_id,
                    SAFE_CAST(JSON_VALUE(raw_data, '$.rating') AS INT64) AS rating,
                    JSON_VALUE(raw_data, '$.title') AS title,
                    JSON_VALUE(raw_data, '$.comment') AS comment,
                    SAFE.TIMESTAMP(JSON_VALUE(raw_data, '$.created_at')) AS created_at,
                    CURRENT_TIMESTAMP() AS processed_at
                FROM `{PROJECT_ID}.bronze.reviews_raw`
                WHERE JSON_VALUE(raw_data, '$.review_id') NOT IN (
                    SELECT review_id FROM `{PROJECT_ID}.silver.reviews`
                )
            """,
            "useLegacySql": False,
        }
    },
    location="EU",
    dag=dag,
)


# ============================================
# Dependencias — orden de ejecución
#
# Customers y Products primero (no dependen de nada)
# Orders después (depende de customers)
# Order Items y Payments después (dependen de orders)
# Events, Inventory, Reviews en paralelo (independientes)
# ============================================

customers_bronze_to_silver >> orders_bronze_to_silver
products_bronze_to_silver >> order_items_bronze_to_silver

orders_bronze_to_silver >> order_items_bronze_to_silver
orders_bronze_to_silver >> payments_bronze_to_silver

# Events, inventory y reviews no dependen de nada — corren en paralelo
```

---

## Paso 6 — Subir el DAG a Composer

```bash
# Obtener el bucket de DAGs
DAG_BUCKET=$(gcloud composer environments describe ecommerce-composer --location=europe-west1 --format="value(config.dagGcsPrefix)")

# Subir el DAG
gsutil cp /Users/appleuser/Desktop/GPC/composer/dags/bronze_to_silver.py "${DAG_BUCKET}/"
```

Verificar:
```bash
gsutil ls "${DAG_BUCKET}/"
```

> Airflow detecta el archivo automáticamente en ~1-2 minutos.

---

## Paso 7 — Abrir la UI de Airflow

```bash
# Obtener la URL de Airflow
gcloud composer environments describe ecommerce-composer \
  --location=europe-west1 \
  --format="value(config.airflowUri)"
```

Abre la URL en el navegador. Verás el dashboard de Airflow con el DAG `bronze_to_silver`.

**Desde consola GCP:**
1. Console → **Composer** → click en `ecommerce-composer`
2. Click en **Open Airflow UI**

---

## Paso 8 — Ejecutar el DAG manualmente

En la UI de Airflow:

1. Busca el DAG `bronze_to_silver`
2. Actívalo con el toggle (si está pausado)
3. Click en el botón **Play** (▶) → **Trigger DAG**
4. Verás los tasks ejecutándose:

```
customers_bronze_to_silver  ✓ Success (12s)
products_bronze_to_silver   ✓ Success (8s)
orders_bronze_to_silver     ✓ Success (15s)     (esperó a customers)
order_items_bronze_to_silver ✓ Success (10s)    (esperó a orders + products)
payments_bronze_to_silver   ✓ Success (9s)      (esperó a orders)
events_bronze_to_silver     ✓ Success (20s)     (corrió en paralelo)
inventory_bronze_to_silver  ✓ Success (5s)      (corrió en paralelo)
reviews_bronze_to_silver    ✓ Success (7s)      (corrió en paralelo)
```

**Desde CLI:**
```bash
gcloud composer environments run ecommerce-composer \
  --location=europe-west1 \
  dags trigger -- bronze_to_silver
```

---

## Paso 9 — Verificar que Silver se llenó

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

Y como Gold son vistas, ahora también tienen datos:

```bash
bq query --use_legacy_sql=false 'SELECT * FROM gold.customer_metrics LIMIT 5'
bq query --use_legacy_sql=false 'SELECT * FROM gold.daily_revenue LIMIT 5'
bq query --use_legacy_sql=false 'SELECT * FROM gold.conversion_funnel LIMIT 5'
```

---

## Paso 10 — Ver logs y monitoreo en Airflow

En la UI de Airflow:

1. Click en el DAG `bronze_to_silver`
2. Click en un task (ej: `customers_bronze_to_silver`)
3. Click en **Log** → verás el query SQL ejecutado y el resultado
4. Pestaña **Graph** → verás el grafo de dependencias visual:

```
customers ─────┐
               ├──▶ orders ──┬──▶ order_items
products ──────┘             └──▶ payments

events ──────────── (paralelo)
inventory ───────── (paralelo)
reviews ─────────── (paralelo)
```

5. Pestaña **Gantt** → verás timeline de cuánto tardó cada task

---

## Paso 11 — APAGAR Composer (ahorrar créditos)

> **MUY IMPORTANTE:** Composer cobra ~$10-15/día aunque no lo uses.
> Después de probar, apágalo.

```bash
gcloud composer environments delete ecommerce-composer \
  --location=europe-west1 \
  --quiet
```

Verificar que se borró:
```bash
gcloud composer environments list --locations=europe-west1
```

> **Los datos en BigQuery (Bronze, Silver, Gold) NO se borran.**
> Solo se borra el entorno de Airflow.

---

## Alternativa gratuita: BigQuery Scheduled Queries

Para dev/testing, en vez de Composer puedes programar los mismos queries directamente en BigQuery:

```bash
bq query --use_legacy_sql=false --schedule="every 6 hours" --display_name="customers_bronze_to_silver" '
INSERT INTO silver.customers
SELECT
    JSON_VALUE(raw_data, "$.id") AS customer_id,
    ...
FROM bronze.customers_raw
WHERE JSON_VALUE(raw_data, "$.id") NOT IN (SELECT customer_id FROM silver.customers)
'
```

O desde la consola: BigQuery → **Scheduled queries** → **Create scheduled query**

| Aspecto | Scheduled Queries | Composer |
|---|---|---|
| Costo | Gratis (solo bytes query) | ~$300/mes |
| Dependencias entre tasks | No | Sí |
| Reintentos | No | Sí |
| UI visual | Básica | Completa (Airflow) |
| Para producción | No (falta orquestación) | Sí |

---

## Checklist

- [ ] API habilitada
- [ ] Entorno Composer creado (tarda ~20 min)
- [ ] Permisos de sa-pipeline configurados
- [ ] DAG creado (`bronze_to_silver.py`)
- [ ] DAG subido al bucket de Composer
- [ ] DAG ejecutado manualmente
- [ ] Silver verificado con datos
- [ ] Gold verificado (vistas funcionando)
- [ ] **Composer apagado después de probar**
