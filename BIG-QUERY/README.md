# BigQuery — Arquitectura Medallion para E-commerce

## Qué es BigQuery

Data warehouse serverless de GCP. No necesitas administrar servidores — solo creas tablas, metes datos y haces queries SQL. Escala automáticamente.

| Aspecto | BigQuery | Análogo AWS |
|---|---|---|
| Qué es | Data warehouse serverless | Redshift / Athena |
| Lenguaje | SQL estándar | SQL |
| Pricing | Por query (bytes escaneados) + storage | Similar |
| Escala | Automática (petabytes) | Manual (Redshift) o automática (Athena) |

## Arquitectura Medallion

Es un patrón de organización de datos en 3 capas:

```
Datos crudos              Datos limpios            Datos listos para negocio
────────────             ──────────────           ─────────────────────────
   BRONZE          →         SILVER          →           GOLD
   (raw)                   (cleaned)                  (aggregated)

- JSON tal cual llega     - Tipado correcto        - Métricas de negocio
- Duplicados              - Sin duplicados         - Tablas para dashboards
- Errores                 - Validado               - KPIs listos
- Sin esquema fijo        - Esquema definido       - Joins hechos
```

### Por qué Medallion

| Sin Medallion | Con Medallion |
|---|---|
| Datos crudos mezclados con reportes | Cada capa tiene un propósito claro |
| Si limpias mal, pierdes el dato original | Bronze siempre tiene el dato crudo (puedes reprocesar) |
| No sabes si un dato es confiable | Gold = datos validados y listos |
| Difícil hacer rollback | Reprocesas Silver/Gold desde Bronze |

---

## Modelo de datos E-commerce

### Entidades principales

```
Customers  →  Orders  →  Order Items  →  Products
    │                        │
    │                   Payments
    │
  Events (clickstream, búsquedas, carrito)
```

### Flujo de datos del E-commerce

```
Tienda web/app
     │
     ├── Cliente se registra         → bronze.customers_raw
     ├── Cliente navega              → bronze.events_raw (page_view, search, add_to_cart)
     ├── Cliente hace pedido         → bronze.orders_raw
     ├── Detalle del pedido          → bronze.order_items_raw
     ├── Cliente paga                → bronze.payments_raw
     ├── Inventario cambia           → bronze.inventory_raw
     └── Reseñas                     → bronze.reviews_raw
```

---

## Plan de Acción

### Paso 1 — Habilitar la API de BigQuery

```bash
gcloud services enable bigquery.googleapis.com
```

### Paso 2 — Crear los datasets (uno por capa)

Un **dataset** en BigQuery es como un "schema" o "base de datos" que agrupa tablas.

```bash
# Bronze — datos crudos
bq mk --dataset --location=us-central1 --description="E-commerce raw data - datos crudos sin procesar" project-dev-490218:bronze

# Silver — datos limpios
bq mk --dataset --location=us-central1 --description="E-commerce cleaned data - datos validados y tipados" project-dev-490218:silver

# Gold — datos de negocio
bq mk --dataset --location=us-central1 --description="E-commerce business data - métricas y KPIs listos" project-dev-490218:gold
```

### Paso 3 — Crear tablas en cada capa

#### Bronze — datos crudos (todo llega como JSON/STRING)

```bash
# Clientes
bq mk --table project-dev-490218:bronze.customers_raw \
  record_id:STRING,\
  raw_data:STRING,\
  source:STRING,\
  ingested_at:TIMESTAMP

# Eventos (clickstream: page_view, search, add_to_cart, remove_from_cart, checkout_start)
bq mk --table project-dev-490218:bronze.events_raw \
  event_id:STRING,\
  event_type:STRING,\
  raw_payload:STRING,\
  source:STRING,\
  ingested_at:TIMESTAMP

# Pedidos
bq mk --table project-dev-490218:bronze.orders_raw \
  record_id:STRING,\
  raw_data:STRING,\
  source:STRING,\
  ingested_at:TIMESTAMP

# Items del pedido
bq mk --table project-dev-490218:bronze.order_items_raw \
  record_id:STRING,\
  raw_data:STRING,\
  source:STRING,\
  ingested_at:TIMESTAMP

# Pagos
bq mk --table project-dev-490218:bronze.payments_raw \
  record_id:STRING,\
  raw_data:STRING,\
  source:STRING,\
  ingested_at:TIMESTAMP

# Productos
bq mk --table project-dev-490218:bronze.products_raw \
  record_id:STRING,\
  raw_data:STRING,\
  source:STRING,\
  ingested_at:TIMESTAMP

# Inventario
bq mk --table project-dev-490218:bronze.inventory_raw \
  record_id:STRING,\
  raw_data:STRING,\
  source:STRING,\
  ingested_at:TIMESTAMP

# Reseñas
bq mk --table project-dev-490218:bronze.reviews_raw \
  record_id:STRING,\
  raw_data:STRING,\
  source:STRING,\
  ingested_at:TIMESTAMP
```

#### Silver — datos limpios (esquema estricto, tipado, sin duplicados)

```bash
# Clientes
bq mk --table project-dev-490218:silver.customers \
  customer_id:STRING,\
  email:STRING,\
  first_name:STRING,\
  last_name:STRING,\
  phone:STRING,\
  country:STRING,\
  city:STRING,\
  address:STRING,\
  created_at:TIMESTAMP,\
  updated_at:TIMESTAMP,\
  processed_at:TIMESTAMP

# Productos
bq mk --table project-dev-490218:silver.products \
  product_id:STRING,\
  name:STRING,\
  description:STRING,\
  category:STRING,\
  subcategory:STRING,\
  price:FLOAT,\
  currency:STRING,\
  sku:STRING,\
  is_active:BOOLEAN,\
  created_at:TIMESTAMP,\
  processed_at:TIMESTAMP

# Pedidos
bq mk --table project-dev-490218:silver.orders \
  order_id:STRING,\
  customer_id:STRING,\
  status:STRING,\
  total_amount:FLOAT,\
  currency:STRING,\
  shipping_address:STRING,\
  shipping_city:STRING,\
  shipping_country:STRING,\
  ordered_at:TIMESTAMP,\
  shipped_at:TIMESTAMP,\
  delivered_at:TIMESTAMP,\
  processed_at:TIMESTAMP

# Items del pedido
bq mk --table project-dev-490218:silver.order_items \
  order_item_id:STRING,\
  order_id:STRING,\
  product_id:STRING,\
  quantity:INTEGER,\
  unit_price:FLOAT,\
  total_price:FLOAT,\
  discount:FLOAT,\
  processed_at:TIMESTAMP

# Pagos
bq mk --table project-dev-490218:silver.payments \
  payment_id:STRING,\
  order_id:STRING,\
  customer_id:STRING,\
  amount:FLOAT,\
  currency:STRING,\
  payment_method:STRING,\
  status:STRING,\
  paid_at:TIMESTAMP,\
  processed_at:TIMESTAMP

# Eventos de clickstream
bq mk --table project-dev-490218:silver.events \
  event_id:STRING,\
  event_type:STRING,\
  customer_id:STRING,\
  session_id:STRING,\
  product_id:STRING,\
  search_query:STRING,\
  page_url:STRING,\
  device:STRING,\
  event_timestamp:TIMESTAMP,\
  processed_at:TIMESTAMP

# Inventario
bq mk --table project-dev-490218:silver.inventory \
  product_id:STRING,\
  warehouse:STRING,\
  quantity_available:INTEGER,\
  quantity_reserved:INTEGER,\
  last_updated:TIMESTAMP,\
  processed_at:TIMESTAMP

# Reseñas
bq mk --table project-dev-490218:silver.reviews \
  review_id:STRING,\
  product_id:STRING,\
  customer_id:STRING,\
  rating:INTEGER,\
  title:STRING,\
  comment:STRING,\
  created_at:TIMESTAMP,\
  processed_at:TIMESTAMP
```

#### Gold — métricas de negocio (agregados listos para dashboards)

```bash
# Revenue diario
bq mk --table project-dev-490218:gold.daily_revenue \
  date:DATE,\
  total_revenue:FLOAT,\
  order_count:INTEGER,\
  avg_order_value:FLOAT,\
  items_sold:INTEGER,\
  unique_customers:INTEGER,\
  currency:STRING

# Métricas por cliente (Customer Lifetime Value)
bq mk --table project-dev-490218:gold.customer_metrics \
  customer_id:STRING,\
  first_name:STRING,\
  last_name:STRING,\
  country:STRING,\
  total_spent:FLOAT,\
  order_count:INTEGER,\
  avg_order_value:FLOAT,\
  first_order_date:TIMESTAMP,\
  last_order_date:TIMESTAMP,\
  days_since_last_order:INTEGER,\
  customer_segment:STRING

# Métricas por producto
bq mk --table project-dev-490218:gold.product_metrics \
  product_id:STRING,\
  product_name:STRING,\
  category:STRING,\
  total_revenue:FLOAT,\
  units_sold:INTEGER,\
  order_count:INTEGER,\
  avg_rating:FLOAT,\
  review_count:INTEGER,\
  return_rate:FLOAT

# KPIs mensuales del negocio
bq mk --table project-dev-490218:gold.monthly_kpis \
  month:DATE,\
  total_revenue:FLOAT,\
  order_count:INTEGER,\
  active_customers:INTEGER,\
  new_customers:INTEGER,\
  returning_customers:INTEGER,\
  avg_order_value:FLOAT,\
  conversion_rate:FLOAT,\
  cart_abandonment_rate:FLOAT

# Funnel de conversión
bq mk --table project-dev-490218:gold.conversion_funnel \
  date:DATE,\
  page_views:INTEGER,\
  product_views:INTEGER,\
  add_to_cart:INTEGER,\
  checkout_started:INTEGER,\
  orders_completed:INTEGER,\
  view_to_cart_rate:FLOAT,\
  cart_to_checkout_rate:FLOAT,\
  checkout_to_purchase_rate:FLOAT

# Top productos por categoría
bq mk --table project-dev-490218:gold.top_products_by_category \
  category:STRING,\
  product_id:STRING,\
  product_name:STRING,\
  total_revenue:FLOAT,\
  units_sold:INTEGER,\
  rank_in_category:INTEGER
```

### Paso 4 — Queries de transformación (Bronze → Silver → Gold)

#### Bronze → Silver (limpiar datos)

```sql
-- Limpiar clientes
INSERT INTO silver.customers
SELECT
  JSON_VALUE(raw_data, '$.id') AS customer_id,
  JSON_VALUE(raw_data, '$.email') AS email,
  JSON_VALUE(raw_data, '$.first_name') AS first_name,
  JSON_VALUE(raw_data, '$.last_name') AS last_name,
  JSON_VALUE(raw_data, '$.phone') AS phone,
  JSON_VALUE(raw_data, '$.country') AS country,
  JSON_VALUE(raw_data, '$.city') AS city,
  JSON_VALUE(raw_data, '$.address') AS address,
  TIMESTAMP(JSON_VALUE(raw_data, '$.created_at')) AS created_at,
  TIMESTAMP(JSON_VALUE(raw_data, '$.updated_at')) AS updated_at,
  CURRENT_TIMESTAMP() AS processed_at
FROM bronze.customers_raw
WHERE JSON_VALUE(raw_data, '$.id') NOT IN (SELECT customer_id FROM silver.customers)
```

```sql
-- Limpiar pedidos
INSERT INTO silver.orders
SELECT
  JSON_VALUE(raw_data, '$.order_id') AS order_id,
  JSON_VALUE(raw_data, '$.customer_id') AS customer_id,
  JSON_VALUE(raw_data, '$.status') AS status,
  CAST(JSON_VALUE(raw_data, '$.total_amount') AS FLOAT64) AS total_amount,
  JSON_VALUE(raw_data, '$.currency') AS currency,
  JSON_VALUE(raw_data, '$.shipping_address') AS shipping_address,
  JSON_VALUE(raw_data, '$.shipping_city') AS shipping_city,
  JSON_VALUE(raw_data, '$.shipping_country') AS shipping_country,
  TIMESTAMP(JSON_VALUE(raw_data, '$.ordered_at')) AS ordered_at,
  TIMESTAMP(JSON_VALUE(raw_data, '$.shipped_at')) AS shipped_at,
  TIMESTAMP(JSON_VALUE(raw_data, '$.delivered_at')) AS delivered_at,
  CURRENT_TIMESTAMP() AS processed_at
FROM bronze.orders_raw
WHERE JSON_VALUE(raw_data, '$.order_id') NOT IN (SELECT order_id FROM silver.orders)
```

```sql
-- Limpiar eventos de clickstream
INSERT INTO silver.events
SELECT
  event_id,
  event_type,
  JSON_VALUE(raw_payload, '$.customer_id') AS customer_id,
  JSON_VALUE(raw_payload, '$.session_id') AS session_id,
  JSON_VALUE(raw_payload, '$.product_id') AS product_id,
  JSON_VALUE(raw_payload, '$.search_query') AS search_query,
  JSON_VALUE(raw_payload, '$.page_url') AS page_url,
  JSON_VALUE(raw_payload, '$.device') AS device,
  TIMESTAMP(JSON_VALUE(raw_payload, '$.timestamp')) AS event_timestamp,
  CURRENT_TIMESTAMP() AS processed_at
FROM bronze.events_raw
WHERE event_id NOT IN (SELECT event_id FROM silver.events)
```

#### Silver → Gold (agregar métricas de negocio)

```sql
-- Revenue diario
INSERT INTO gold.daily_revenue
SELECT
  DATE(ordered_at) AS date,
  SUM(total_amount) AS total_revenue,
  COUNT(DISTINCT order_id) AS order_count,
  AVG(total_amount) AS avg_order_value,
  SUM(oi.quantity) AS items_sold,
  COUNT(DISTINCT customer_id) AS unique_customers,
  o.currency
FROM silver.orders o
JOIN silver.order_items oi ON o.order_id = oi.order_id
WHERE o.status IN ('completed', 'delivered')
GROUP BY DATE(ordered_at), o.currency
```

```sql
-- Customer Lifetime Value
INSERT INTO gold.customer_metrics
SELECT
  c.customer_id,
  c.first_name,
  c.last_name,
  c.country,
  SUM(o.total_amount) AS total_spent,
  COUNT(DISTINCT o.order_id) AS order_count,
  AVG(o.total_amount) AS avg_order_value,
  MIN(o.ordered_at) AS first_order_date,
  MAX(o.ordered_at) AS last_order_date,
  DATE_DIFF(CURRENT_DATE(), DATE(MAX(o.ordered_at)), DAY) AS days_since_last_order,
  CASE
    WHEN COUNT(DISTINCT o.order_id) >= 10 THEN 'VIP'
    WHEN COUNT(DISTINCT o.order_id) >= 5 THEN 'Loyal'
    WHEN COUNT(DISTINCT o.order_id) >= 2 THEN 'Returning'
    ELSE 'New'
  END AS customer_segment
FROM silver.customers c
LEFT JOIN silver.orders o ON c.customer_id = o.customer_id
WHERE o.status IN ('completed', 'delivered')
GROUP BY c.customer_id, c.first_name, c.last_name, c.country
```

```sql
-- Funnel de conversión diario
INSERT INTO gold.conversion_funnel
SELECT
  DATE(event_timestamp) AS date,
  COUNTIF(event_type = 'page_view') AS page_views,
  COUNTIF(event_type = 'product_view') AS product_views,
  COUNTIF(event_type = 'add_to_cart') AS add_to_cart,
  COUNTIF(event_type = 'checkout_start') AS checkout_started,
  COUNTIF(event_type = 'purchase') AS orders_completed,
  SAFE_DIVIDE(COUNTIF(event_type = 'add_to_cart'), COUNTIF(event_type = 'product_view')) AS view_to_cart_rate,
  SAFE_DIVIDE(COUNTIF(event_type = 'checkout_start'), COUNTIF(event_type = 'add_to_cart')) AS cart_to_checkout_rate,
  SAFE_DIVIDE(COUNTIF(event_type = 'purchase'), COUNTIF(event_type = 'checkout_start')) AS checkout_to_purchase_rate
FROM silver.events
GROUP BY DATE(event_timestamp)
```

```sql
-- KPIs mensuales
INSERT INTO gold.monthly_kpis
SELECT
  DATE_TRUNC(ordered_at, MONTH) AS month,
  SUM(total_amount) AS total_revenue,
  COUNT(DISTINCT order_id) AS order_count,
  COUNT(DISTINCT customer_id) AS active_customers,
  COUNT(DISTINCT CASE
    WHEN DATE_TRUNC(ordered_at, MONTH) = DATE_TRUNC(
      (SELECT MIN(ordered_at) FROM silver.orders o2 WHERE o2.customer_id = o.customer_id), MONTH)
    THEN customer_id END) AS new_customers,
  COUNT(DISTINCT CASE
    WHEN DATE_TRUNC(ordered_at, MONTH) > DATE_TRUNC(
      (SELECT MIN(ordered_at) FROM silver.orders o2 WHERE o2.customer_id = o.customer_id), MONTH)
    THEN customer_id END) AS returning_customers,
  AVG(total_amount) AS avg_order_value,
  NULL AS conversion_rate,
  NULL AS cart_abandonment_rate
FROM silver.orders o
WHERE status IN ('completed', 'delivered')
GROUP BY DATE_TRUNC(ordered_at, MONTH)
```

### Paso 5 — Permisos IAM para BigQuery

Agregar a `infra/iam.tf` los roles de BigQuery:

| SA | Rol | Para qué |
|---|---|---|
| `sa-pipeline` | `roles/bigquery.admin` | Crear datasets y tablas via Terraform |
| `sa-cloudrun` | `roles/bigquery.dataEditor` | Insertar datos desde la API (Bronze) |
| `sa-functions` | `roles/bigquery.dataEditor` | Transformar datos (Silver, Gold) |
| `sa-monitoring` | `roles/bigquery.dataViewer` | Leer datos para dashboards |

### Paso 6 — Definir en Terraform

Agregar los datasets y tablas en `infra/bigquery.tf` para que el pipeline los cree automáticamente.

### Paso 7 — Conectar con Pub/Sub (siguiente módulo)

```
Tienda web/app
     │
     ├── Evento: cliente navega      → Pub/Sub topic "events"
     ├── Evento: cliente compra      → Pub/Sub topic "orders"
     └── Evento: pago procesado      → Pub/Sub topic "payments"
                    │
             Dataflow / Beam
                    │
             BigQuery Bronze
                    │
              SQL transforms
                    │
             Silver → Gold
                    │
         Dashboard / API (Cloud Run)
```

---

## Verificar

```bash
# Listar datasets
bq ls

# Listar tablas en un dataset
bq ls bronze
bq ls silver
bq ls gold

# Hacer un query de prueba
bq query --use_legacy_sql=false 'SELECT * FROM bronze.events_raw LIMIT 10'
```

---

## Cómo se conecta con el resto del stack

```
              Tienda Web / App
                    │
            ┌───────▼───────┐
            │    Pub/Sub    │  ← eventos en tiempo real
            └───────┬───────┘
                    │
            ┌───────▼───────┐
            │   Dataflow    │  ← procesa y escribe en Bronze
            └───────┬───────┘
                    │
   ┌────────────────▼─────────────────┐
   │           BigQuery               │
   │                                  │
   │  Bronze (8 tablas)               │
   │  ├── customers_raw               │
   │  ├── events_raw (clickstream)    │
   │  ├── orders_raw                  │
   │  ├── order_items_raw             │
   │  ├── payments_raw                │
   │  ├── products_raw                │
   │  ├── inventory_raw               │
   │  └── reviews_raw                 │
   │         │                        │
   │         │ SQL transform          │
   │         ▼                        │
   │  Silver (8 tablas)               │
   │  ├── customers                   │
   │  ├── events                      │
   │  ├── orders                      │
   │  ├── order_items                 │
   │  ├── payments                    │
   │  ├── products                    │
   │  ├── inventory                   │
   │  └── reviews                     │
   │         │                        │
   │         │ SQL aggregate          │
   │         ▼                        │
   │  Gold (6 tablas)                 │
   │  ├── daily_revenue               │
   │  ├── customer_metrics (CLV)      │
   │  ├── product_metrics             │
   │  ├── monthly_kpis                │
   │  ├── conversion_funnel           │
   │  └── top_products_by_category    │
   │                                  │
   └──────────────┬───────────────────┘
                  │
          ┌───────▼───────┐
          │   Cloud Run   │  ← API expone datos Gold
          └───────┬───────┘
                  │
          ┌───────▼───────┐
          │   Looker /    │  ← Dashboards de negocio
          │  Data Studio  │
          └───────────────┘
```

---

## Resumen — Orden de ejecución

| Paso | Qué | Cuándo |
|---|---|---|
| 1 | Habilitar API de BigQuery | Ahora |
| 2 | Crear datasets (bronze, silver, gold) | Ahora |
| 3 | Crear tablas (8 bronze, 8 silver, 6 gold) | Ahora |
| 4 | Queries de transformación | Cuando haya datos |
| 5 | Permisos IAM | Agregar a iam.tf |
| 6 | Definir en Terraform (bigquery.tf) | Agregar al pipeline |
| 7 | Conectar con Pub/Sub + Dataflow | Siguiente módulo |

---

## Errores comunes

| Error | Causa | Solución |
|---|---|---|
| `Not found: Dataset` | Dataset no existe o proyecto equivocado | Verificar con `bq ls` y `gcloud config get project` |
| `Access Denied` | La SA no tiene rol de BigQuery | Agregar `bigquery.dataEditor` o `bigquery.admin` |
| Query caro (muchos bytes) | Escaneó toda la tabla | Usar particiones por fecha y filtrar |
| Datos duplicados en Silver | No se filtró duplicados en la transformación | Usar `WHERE id NOT IN (SELECT id FROM silver.tabla)` |
| `JSON_VALUE returns NULL` | El campo no existe en el JSON crudo | Verificar estructura del JSON en Bronze |
