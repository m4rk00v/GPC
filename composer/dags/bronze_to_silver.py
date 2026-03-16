"""
DAG: bronze_to_silver
Orquesta la transformación de datos crudos (Bronze) a datos limpios (Silver).

Flujo:
  1. Parsea JSON de Bronze con MERGE (no NOT IN — evita problemas con NULLs)
  2. Valida tipos (STRING → TIMESTAMP, FLOAT64, etc.)
  3. Deduplica registros (MERGE solo inserta si no existe)
  4. Inserta en Silver

Dependencias:
  customers ─────┐
                 ├──▶ orders ──┬──▶ order_items
  products ──────┘             └──▶ payments
  events ──────────── (paralelo)
  inventory ───────── (paralelo)
  reviews ─────────── (paralelo)

Frecuencia: cada 3 minutos (demo) — en producción: cada 6 horas
Patrón: MERGE (evita NOT IN que falla con NULLs y es lento a escala)
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.providers.google.cloud.operators.bigquery import BigQueryInsertJobOperator

PROJECT_ID = "project-dev-490218"

default_args = {
    "owner": "data-team",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=1),  # 1 min para demo (producción: 5 min)
}

dag = DAG(
    dag_id="bronze_to_silver",
    default_args=default_args,
    description="Transforma datos crudos de Bronze a Silver (limpia, parsea, deduplica)",
    schedule_interval="*/3 * * * *",  # Cada 3 minutos (demo) — producción: "0 */6 * * *"
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["ecommerce", "medallion", "bronze-to-silver"],
)

# --- Customers: MERGE Bronze → Silver ---
customers_bronze_to_silver = BigQueryInsertJobOperator(
    task_id="customers_bronze_to_silver",
    configuration={
        "query": {
            "query": f"""
                MERGE INTO `{PROJECT_ID}.silver.customers` AS target
                USING (
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
                ) AS source
                ON target.customer_id = source.customer_id
                WHEN NOT MATCHED THEN
                    INSERT (customer_id, email, first_name, last_name, phone, country, city, address, created_at, updated_at, processed_at)
                    VALUES (source.customer_id, source.email, source.first_name, source.last_name, source.phone, source.country, source.city, source.address, source.created_at, source.updated_at, source.processed_at)
                WHEN MATCHED THEN
                    UPDATE SET
                        email = source.email,
                        first_name = source.first_name,
                        last_name = source.last_name,
                        phone = source.phone,
                        country = source.country,
                        city = source.city,
                        address = source.address,
                        updated_at = source.updated_at,
                        processed_at = source.processed_at
            """,
            "useLegacySql": False,
        }
    },
    location="EU",
    dag=dag,
)

# --- Products: MERGE Bronze → Silver ---
products_bronze_to_silver = BigQueryInsertJobOperator(
    task_id="products_bronze_to_silver",
    configuration={
        "query": {
            "query": f"""
                MERGE INTO `{PROJECT_ID}.silver.products` AS target
                USING (
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
                ) AS source
                ON target.product_id = source.product_id
                WHEN NOT MATCHED THEN
                    INSERT (product_id, name, description, category, subcategory, price, currency, sku, is_active, created_at, processed_at)
                    VALUES (source.product_id, source.name, source.description, source.category, source.subcategory, source.price, source.currency, source.sku, source.is_active, source.created_at, source.processed_at)
                WHEN MATCHED THEN
                    UPDATE SET
                        name = source.name,
                        description = source.description,
                        price = source.price,
                        is_active = source.is_active,
                        processed_at = source.processed_at
            """,
            "useLegacySql": False,
        }
    },
    location="EU",
    dag=dag,
)

# --- Orders: MERGE Bronze → Silver ---
orders_bronze_to_silver = BigQueryInsertJobOperator(
    task_id="orders_bronze_to_silver",
    configuration={
        "query": {
            "query": f"""
                MERGE INTO `{PROJECT_ID}.silver.orders` AS target
                USING (
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
                ) AS source
                ON target.order_id = source.order_id
                WHEN NOT MATCHED THEN
                    INSERT (order_id, customer_id, status, total_amount, currency, shipping_address, shipping_city, shipping_country, ordered_at, shipped_at, delivered_at, processed_at)
                    VALUES (source.order_id, source.customer_id, source.status, source.total_amount, source.currency, source.shipping_address, source.shipping_city, source.shipping_country, source.ordered_at, source.shipped_at, source.delivered_at, source.processed_at)
                WHEN MATCHED THEN
                    UPDATE SET
                        status = source.status,
                        shipped_at = source.shipped_at,
                        delivered_at = source.delivered_at,
                        processed_at = source.processed_at
            """,
            "useLegacySql": False,
        }
    },
    location="EU",
    dag=dag,
)

# --- Events: MERGE Bronze → Silver ---
events_bronze_to_silver = BigQueryInsertJobOperator(
    task_id="events_bronze_to_silver",
    configuration={
        "query": {
            "query": f"""
                MERGE INTO `{PROJECT_ID}.silver.events` AS target
                USING (
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
                ) AS source
                ON target.event_id = source.event_id
                WHEN NOT MATCHED THEN
                    INSERT (event_id, event_type, customer_id, session_id, product_id, search_query, page_url, device, event_timestamp, processed_at)
                    VALUES (source.event_id, source.event_type, source.customer_id, source.session_id, source.product_id, source.search_query, source.page_url, source.device, source.event_timestamp, source.processed_at)
            """,
            "useLegacySql": False,
        }
    },
    location="EU",
    dag=dag,
)

# --- Payments: MERGE Bronze → Silver ---
payments_bronze_to_silver = BigQueryInsertJobOperator(
    task_id="payments_bronze_to_silver",
    configuration={
        "query": {
            "query": f"""
                MERGE INTO `{PROJECT_ID}.silver.payments` AS target
                USING (
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
                ) AS source
                ON target.payment_id = source.payment_id
                WHEN NOT MATCHED THEN
                    INSERT (payment_id, order_id, customer_id, amount, currency, payment_method, status, paid_at, processed_at)
                    VALUES (source.payment_id, source.order_id, source.customer_id, source.amount, source.currency, source.payment_method, source.status, source.paid_at, source.processed_at)
                WHEN MATCHED THEN
                    UPDATE SET
                        status = source.status,
                        processed_at = source.processed_at
            """,
            "useLegacySql": False,
        }
    },
    location="EU",
    dag=dag,
)

# --- Order Items: MERGE Bronze → Silver ---
order_items_bronze_to_silver = BigQueryInsertJobOperator(
    task_id="order_items_bronze_to_silver",
    configuration={
        "query": {
            "query": f"""
                MERGE INTO `{PROJECT_ID}.silver.order_items` AS target
                USING (
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
                ) AS source
                ON target.order_item_id = source.order_item_id
                WHEN NOT MATCHED THEN
                    INSERT (order_item_id, order_id, product_id, quantity, unit_price, total_price, discount, processed_at)
                    VALUES (source.order_item_id, source.order_id, source.product_id, source.quantity, source.unit_price, source.total_price, source.discount, source.processed_at)
            """,
            "useLegacySql": False,
        }
    },
    location="EU",
    dag=dag,
)

# --- Inventory: MERGE Bronze → Silver ---
inventory_bronze_to_silver = BigQueryInsertJobOperator(
    task_id="inventory_bronze_to_silver",
    configuration={
        "query": {
            "query": f"""
                MERGE INTO `{PROJECT_ID}.silver.inventory` AS target
                USING (
                    SELECT
                        JSON_VALUE(raw_data, '$.product_id') AS product_id,
                        JSON_VALUE(raw_data, '$.warehouse') AS warehouse,
                        SAFE_CAST(JSON_VALUE(raw_data, '$.quantity_available') AS INT64) AS quantity_available,
                        SAFE_CAST(JSON_VALUE(raw_data, '$.quantity_reserved') AS INT64) AS quantity_reserved,
                        SAFE.TIMESTAMP(JSON_VALUE(raw_data, '$.last_updated')) AS last_updated,
                        CURRENT_TIMESTAMP() AS processed_at
                    FROM `{PROJECT_ID}.bronze.inventory_raw`
                ) AS source
                ON target.product_id = source.product_id AND target.warehouse = source.warehouse
                WHEN NOT MATCHED THEN
                    INSERT (product_id, warehouse, quantity_available, quantity_reserved, last_updated, processed_at)
                    VALUES (source.product_id, source.warehouse, source.quantity_available, source.quantity_reserved, source.last_updated, source.processed_at)
                WHEN MATCHED THEN
                    UPDATE SET
                        quantity_available = source.quantity_available,
                        quantity_reserved = source.quantity_reserved,
                        last_updated = source.last_updated,
                        processed_at = source.processed_at
            """,
            "useLegacySql": False,
        }
    },
    location="EU",
    dag=dag,
)

# --- Reviews: MERGE Bronze → Silver ---
reviews_bronze_to_silver = BigQueryInsertJobOperator(
    task_id="reviews_bronze_to_silver",
    configuration={
        "query": {
            "query": f"""
                MERGE INTO `{PROJECT_ID}.silver.reviews` AS target
                USING (
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
                ) AS source
                ON target.review_id = source.review_id
                WHEN NOT MATCHED THEN
                    INSERT (review_id, product_id, customer_id, rating, title, comment, created_at, processed_at)
                    VALUES (source.review_id, source.product_id, source.customer_id, source.rating, source.title, source.comment, source.created_at, source.processed_at)
            """,
            "useLegacySql": False,
        }
    },
    location="EU",
    dag=dag,
)

# ============================================
# Dependencias — orden de ejecución
# ============================================

customers_bronze_to_silver >> orders_bronze_to_silver
products_bronze_to_silver >> order_items_bronze_to_silver
orders_bronze_to_silver >> order_items_bronze_to_silver
orders_bronze_to_silver >> payments_bronze_to_silver
