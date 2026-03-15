# BigQuery E-commerce — Step by Step

## Arquitectura completa — GCP Data LakeHouse

```
┌──────────────────────┐
│ Users / Apps         │
│ Clientes internos    │
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐        ┌──────────────────────┐
│ Streaming Data       │───────▶│ Ingestor Process     │
│ Topics               │        │ (Dataflow)           │──────┐
│ (Pub/Sub)            │        └──────────────────────┘      │
└──────────────────────┘                                      │
                                                              ▼
┌──────────────┐                                  ┌───────────────────────┐
│  Cloud SQL   │──── External Federated Queries ─▶│                       │
│ (PostgreSQL) │                                  │    LakeHouse          │     ┌─────────────────────┐
└──────┬───────┘                                  │    (BigQuery)         │────▶│ Consumption         │
       │                                          │                       │     │ Projects            │
       │         ┌──────────────────────┐         │  Bronze → Silver →   │     │ (BigQuery)          │
       └────────▶│ Batch ETLs          │────────▶│  Gold                │     └─────────────────────┘
                 │ (Dataflow)          │         │                       │
┌──────────────┐ └──────────────────────┘         └───────────┬──────────┘
│ Cloud        │          ▲                                   │
│ Storage      │──────────┘                                   │
└──────────────┘                                              ▼
                 ┌──────────────────────┐         ┌───────────────────────┐
                 │ Batch Orchestrator   │         │ Analytics Cross       │
                 │ (Cloud Composer /    │         │ Reports               │
                 │  Airflow)           │         │ (Looker)              │
                 └──────────────────────┘         └───────────────────────┘

                          ┌─────────────────────────────────┐
                          │  Governance & Security Layer     │
                          │  ┌──────────────┐ ┌───────────┐ │
                          │  │ Data Catalog │ │ Dataplex  │ │
                          │  └──────────────┘ └───────────┘ │
                          └─────────────────────────────────┘
```

### Componentes y su rol

| Componente | Servicio GCP | Qué hace | Módulo |
|---|---|---|---|
| **Streaming Data Topics** | Pub/Sub | Recibe eventos en tiempo real (clicks, compras) | Hora 4 |
| **Ingestor Process** | Dataflow | Procesa streaming y escribe en BigQuery Bronze | Hora 5-6 |
| **LakeHouse** | BigQuery | Almacena y transforma datos (Bronze → Silver → Gold) | Hora 3 (ahora) |
| **Batch ETLs** | Dataflow | Copia datos de Cloud SQL / Storage a BigQuery en lotes | Hora 5-6 |
| **Batch Orchestrator** | Cloud Composer (Airflow) | Programa y orquesta los ETLs batch | Hora 8 |
| **Cloud SQL** | PostgreSQL | Base de datos de la app (transaccional) | Hora 3 |
| **Cloud Storage** | GCS | Archivos: CSVs, imágenes, exports | Hora 3 |
| **External Federated Queries** | BigQuery | Consultar Cloud SQL desde BigQuery sin copiar datos | Hora 3 |
| **Consumption Projects** | BigQuery | Proyectos separados para equipos que consumen datos | Hora 3 |
| **Analytics Cross Reports** | Looker | Dashboards y reportes de negocio | Hora 9 |
| **Data Catalog** | Data Catalog | Metadatos: qué tablas existen, qué significan | Hora 7 |
| **Dataplex** | Dataplex | Governance: quién puede ver qué, calidad de datos | Hora 7 |

### Dos caminos para que los datos lleguen a BigQuery

| Camino | Cuándo se usa | Ejemplo E-commerce |
|---|---|---|
| **Streaming** (Pub/Sub → Dataflow → BigQuery) | Datos en tiempo real, baja latencia | Clicks, búsquedas, add_to_cart, compras |
| **Batch** (Cloud SQL/Storage → Dataflow → BigQuery) | Datos históricos, cargas programadas | Catálogo de productos, dump diario de usuarios, CSVs de proveedores |
| **Federated Queries** | Consultar sin copiar (datos pequeños o ad-hoc) | Query directo a Cloud SQL desde BigQuery |

---

## BigQuery NO es una base de datos relacional

BigQuery es un **data warehouse columnar** para análisis, no para correr tu app.

| Aspecto | Cloud SQL (PostgreSQL) | BigQuery |
|---|---|---|
| **Tipo** | OLTP (transacciones) | OLAP (análisis) |
| **Motor** | PostgreSQL / MySQL | Dremel (motor propio de Google) |
| **Almacenamiento** | Por filas | Por columnas |
| **Índices** | Sí (B-tree, etc.) | No — escanea columnas completas |
| **Foreign keys** | Sí (constraints) | No — joins manuales con SQL |
| **Para qué** | La app: INSERT/UPDATE rápidos, carrito, login, inventario | Analytics: reportes, KPIs, dashboards |
| **Escala** | Vertical (más RAM/CPU) | Automática (petabytes) |
| **Precio** | Por hora (instancia encendida) | Por query (bytes escaneados) + storage |

### En tu stack E-commerce son dos cosas distintas:

```
Cliente compra en la tienda
         │
         ▼
   Cloud SQL (PostgreSQL)         ← la app funciona aquí (tiempo real)
   - users, orders, cart,
     inventory, payments
         │
         │ copia / streaming
         ▼
   BigQuery                       ← analytics aquí (reportes)
   - Bronze (datos crudos)
   - Silver (datos limpios)
   - Gold (KPIs y dashboards)
```

> **Cloud SQL** = donde vive tu app (lectura/escritura rápida)
> **BigQuery** = donde analizas los datos (queries sobre millones de filas)

### Tablas: cuál va en cada lado

| Tabla | PostgreSQL (Cloud SQL) | BigQuery Bronze | BigQuery Silver | BigQuery Gold |
|---|---|---|---|---|
| **users / customers** | `users` — login, registro, perfil | `customers_raw` — copia cruda JSON | `customers` — limpio, tipado | `customer_metrics` — CLV, segmentación |
| **products** | `products` — catálogo, búsqueda, precios | `products_raw` — copia cruda JSON | `products` — limpio, tipado | `product_metrics` — ventas, rating |
| **orders** | `orders` — crear/actualizar pedidos | `orders_raw` — copia cruda JSON | `orders` — limpio, tipado | `daily_revenue`, `monthly_kpis` |
| **order_items** | `order_items` — detalle del pedido | `order_items_raw` — copia cruda JSON | `order_items` — limpio, tipado | (se usa en joins para Gold) |
| **payments** | `payments` — procesar pagos | `payments_raw` — copia cruda JSON | `payments` — limpio, tipado | (se usa en joins para Gold) |
| **cart** | `cart` — carrito de compras | No se copia (dato temporal) | — | — |
| **inventory** | `inventory` — stock en tiempo real | `inventory_raw` — copia cruda JSON | `inventory` — limpio, tipado | (alertas de stock bajo) |
| **reviews** | `reviews` — reseñas de productos | `reviews_raw` — copia cruda JSON | `reviews` — limpio, tipado | `product_metrics` — avg rating |
| **sessions** | `sessions` — sesiones activas | No se copia (dato temporal) | — | — |
| **events (clickstream)** | No existe aquí — va directo a BigQuery | `events_raw` — clickstream crudo | `events` — limpio, tipado | `conversion_funnel` |

> **Nota:** `cart` y `sessions` son datos temporales que solo viven en PostgreSQL.
> `events` (clickstream) va directo a BigQuery via Pub/Sub — no pasa por PostgreSQL.

### Cómo llegan los datos a BigQuery (automático, no manual)

```
PostgreSQL                    Pub/Sub                    BigQuery
──────────                   ─────────                  ────────
INSERT/UPDATE en orders  →   Evento "order.created"  →  bronze.orders_raw
INSERT en payments       →   Evento "payment.done"   →  bronze.payments_raw
UPDATE en inventory      →   Evento "stock.changed"  →  bronze.inventory_raw

Navegador del cliente                                   BigQuery
─────────────────────                                  ────────
Click, búsqueda, carrito →  Pub/Sub "events"        →  bronze.events_raw
```

---

## Paso 1 — Habilitar la API

```bash
gcloud services enable bigquery.googleapis.com
```

Verificar:
```bash
gcloud services list --enabled | grep bigquery
```

---

## Paso 2 — Crear los 3 datasets (región EU para GDPR)

> **Buena práctica:** Siempre región EU para datos de ciudadanos europeos — es requisito GDPR.
> **Problema que evitas:** Transferencia internacional de datos sin base legal — multa de hasta 4% facturación global.

```bash
bq mk --dataset --location=EU --description="E-commerce raw data - datos crudos sin procesar" project-dev-490218:bronze
```

```bash
bq mk --dataset --location=EU --description="E-commerce cleaned data - datos validados y tipados" project-dev-490218:silver
```

```bash
bq mk --dataset --location=EU --description="E-commerce business metrics - KPIs y dashboards" project-dev-490218:gold
```

Verificar:
```bash
bq ls
bq show bronze
```



  BigQuery
  ├── bronze (dataset)     ← como "CREATE SCHEMA bronze" en PostgreSQL
  │   ├── customers_raw
  │   ├── orders_raw
  │   └── ...
  ├── silver (dataset)     ← como "CREATE SCHEMA silver"
  │   ├── customers
  │   ├── orders
  │   └── ...
  └── gold (dataset)       ← como "CREATE SCHEMA gold"
      ├── daily_revenue (vista)
      ├── customer_metrics (vista)
      └── ...

  ┌──────────┬────────────────────────┬─────────────────────────────┐
  │ Concepto │       PostgreSQL       │          BigQuery           │
  ├──────────┼────────────────────────┼─────────────────────────────┤
  │ Proyecto │ Servidor/Instancia     │ project-dev-490218          │
  ├──────────┼────────────────────────┼─────────────────────────────┤
  │ Dataset  │ Schema (CREATE SCHEMA) │ bronze, silver, gold        │
  ├──────────┼────────────────────────┼─────────────────────────────┤
  │ Tabla    │ Tabla                  │ customers_raw, orders, etc. │

  

---

## Paso 3 — Crear tablas Bronze con esquema explícito

> **Buena práctica:** Nunca usar `autodetect=True` en producción — define el esquema explícitamente.
> **Problema que evitas:** BigQuery infiere STRING para columnas numéricas y rompe queries analíticas downstream.

```bash
bq mk --table project-dev-490218:bronze.customers_raw record_id:STRING,raw_data:STRING,source:STRING,ingested_at:TIMESTAMP
```

```bash
bq mk --table project-dev-490218:bronze.events_raw event_id:STRING,event_type:STRING,raw_payload:STRING,source:STRING,ingested_at:TIMESTAMP
```

```bash
bq mk --table project-dev-490218:bronze.orders_raw record_id:STRING,raw_data:STRING,source:STRING,ingested_at:TIMESTAMP
```

```bash
bq mk --table project-dev-490218:bronze.order_items_raw record_id:STRING,raw_data:STRING,source:STRING,ingested_at:TIMESTAMP
```

```bash
bq mk --table project-dev-490218:bronze.payments_raw record_id:STRING,raw_data:STRING,source:STRING,ingested_at:TIMESTAMP
```

```bash
bq mk --table project-dev-490218:bronze.products_raw record_id:STRING,raw_data:STRING,source:STRING,ingested_at:TIMESTAMP
```

```bash
bq mk --table project-dev-490218:bronze.inventory_raw record_id:STRING,raw_data:STRING,source:STRING,ingested_at:TIMESTAMP
```

```bash
bq mk --table project-dev-490218:bronze.reviews_raw record_id:STRING,raw_data:STRING,source:STRING,ingested_at:TIMESTAMP
```

Verificar:
```bash
bq ls bronze
```

---

## Paso 4 — Crear tablas Silver con PARTITION y CLUSTER

> **PARTITION BY DATE:** Análogo a SORTKEY en Redshift. Siempre particionar tablas que superen 1 GB o que se consulten por rango de fechas.
> **Problema que evitas:** Queries que escanean la tabla completa — en BigQuery pagas por bytes escaneados.

> **CLUSTER BY:** Análogo a DISTKEY en Redshift. Máximo 4 columnas — ordenar de mayor a menor cardinalidad.
> **Problema que evitas:** Clustering inefectivo que no reduce el escaneo de datos.

Las tablas Silver se crean con SQL para usar PARTITION y CLUSTER:

```bash
bq query --use_legacy_sql=false '
CREATE TABLE silver.customers (
  customer_id STRING NOT NULL,
  email STRING,
  first_name STRING,
  last_name STRING,
  phone STRING,
  country STRING,
  city STRING,
  address STRING,
  created_at TIMESTAMP,
  updated_at TIMESTAMP,
  processed_at TIMESTAMP
)
CLUSTER BY country, city
'
```

```bash
bq query --use_legacy_sql=false '
CREATE TABLE silver.products (
  product_id STRING NOT NULL,
  name STRING,
  description STRING,
  category STRING,
  subcategory STRING,
  price FLOAT64,
  currency STRING,
  sku STRING,
  is_active BOOL,
  created_at TIMESTAMP,
  processed_at TIMESTAMP
)
CLUSTER BY category, subcategory
'
```

```bash
bq query --use_legacy_sql=false '
CREATE TABLE silver.orders (
  order_id STRING NOT NULL,
  customer_id STRING,
  status STRING,
  total_amount FLOAT64,
  currency STRING,
  shipping_address STRING,
  shipping_city STRING,
  shipping_country STRING,
  ordered_at TIMESTAMP,
  shipped_at TIMESTAMP,
  delivered_at TIMESTAMP,
  processed_at TIMESTAMP
)
PARTITION BY DATE(ordered_at)
CLUSTER BY status, shipping_country
'
```

```bash
bq query --use_legacy_sql=false '
CREATE TABLE silver.order_items (
  order_item_id STRING NOT NULL,
  order_id STRING,
  product_id STRING,
  quantity INT64,
  unit_price FLOAT64,
  total_price FLOAT64,
  discount FLOAT64,
  processed_at TIMESTAMP
)
CLUSTER BY product_id
'
```

```bash
bq query --use_legacy_sql=false '
CREATE TABLE silver.payments (
  payment_id STRING NOT NULL,
  order_id STRING,
  customer_id STRING,
  amount FLOAT64,
  currency STRING,
  payment_method STRING,
  status STRING,
  paid_at TIMESTAMP,
  processed_at TIMESTAMP
)
PARTITION BY DATE(paid_at)
CLUSTER BY payment_method, status
'
```

```bash
bq query --use_legacy_sql=false '
CREATE TABLE silver.events (
  event_id STRING NOT NULL,
  event_type STRING,
  customer_id STRING,
  session_id STRING,
  product_id STRING,
  search_query STRING,
  page_url STRING,
  device STRING,
  event_timestamp TIMESTAMP,
  processed_at TIMESTAMP
)
PARTITION BY DATE(event_timestamp)
CLUSTER BY event_type, customer_id, device
'
```

```bash
bq query --use_legacy_sql=false '
CREATE TABLE silver.inventory (
  product_id STRING NOT NULL,
  warehouse STRING,
  quantity_available INT64,
  quantity_reserved INT64,
  last_updated TIMESTAMP,
  processed_at TIMESTAMP
)
CLUSTER BY warehouse
'
```

```bash
bq query --use_legacy_sql=false '
CREATE TABLE silver.reviews (
  review_id STRING NOT NULL,
  product_id STRING,
  customer_id STRING,
  rating INT64,
  title STRING,
  comment STRING,
  created_at TIMESTAMP,
  processed_at TIMESTAMP
)
PARTITION BY DATE(created_at)
CLUSTER BY product_id, rating
'
```

Verificar particiones y clusters:
```bash
bq show --schema silver.orders
bq show --format=prettyjson silver.orders | grep -A5 "timePartitioning\|clustering"
```

---

## Paso 5 — Crear vistas Gold (no tablas)

> **Buena práctica:** Gold usa **vistas** (views) en vez de tablas. La vista recalcula siempre desde Silver — no hay datos duplicados, no hay sincronización.
> **Buena práctica:** Usar vistas autorizadas para dar acceso a Gold sin exponer Silver.
> **Problema que evitas:** Usuarios que acceden directamente a Silver y ven datos sin desidentificar.

```bash
bq query --use_legacy_sql=false '
CREATE OR REPLACE VIEW gold.daily_revenue AS
SELECT
  DATE(o.ordered_at) AS date,
  SUM(o.total_amount) AS total_revenue,
  COUNT(DISTINCT o.order_id) AS order_count,
  AVG(o.total_amount) AS avg_order_value,
  SUM(oi.quantity) AS items_sold,
  COUNT(DISTINCT o.customer_id) AS unique_customers,
  o.currency
FROM silver.orders o
JOIN silver.order_items oi ON o.order_id = oi.order_id
WHERE o.status IN ("completed", "delivered")
GROUP BY DATE(o.ordered_at), o.currency
'
```

```bash
bq query --use_legacy_sql=false '
CREATE OR REPLACE VIEW gold.customer_metrics AS
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
    WHEN COUNT(DISTINCT o.order_id) >= 10 THEN "VIP"
    WHEN COUNT(DISTINCT o.order_id) >= 5 THEN "Loyal"
    WHEN COUNT(DISTINCT o.order_id) >= 2 THEN "Returning"
    ELSE "New"
  END AS customer_segment
FROM silver.customers c
LEFT JOIN silver.orders o ON c.customer_id = o.customer_id
WHERE o.status IN ("completed", "delivered")
GROUP BY c.customer_id, c.first_name, c.last_name, c.country
'
```

```bash
bq query --use_legacy_sql=false '
CREATE OR REPLACE VIEW gold.product_metrics AS
SELECT
  p.product_id,
  p.name AS product_name,
  p.category,
  COALESCE(SUM(oi.total_price), 0) AS total_revenue,
  COALESCE(SUM(oi.quantity), 0) AS units_sold,
  COUNT(DISTINCT oi.order_id) AS order_count,
  AVG(r.rating) AS avg_rating,
  COUNT(DISTINCT r.review_id) AS review_count
FROM silver.products p
LEFT JOIN silver.order_items oi ON p.product_id = oi.product_id
LEFT JOIN silver.reviews r ON p.product_id = r.product_id
GROUP BY p.product_id, p.name, p.category
'
```

```bash
bq query --use_legacy_sql=false '
CREATE OR REPLACE VIEW gold.conversion_funnel AS
SELECT
  DATE(event_timestamp) AS date,
  COUNTIF(event_type = "page_view") AS page_views,
  COUNTIF(event_type = "product_view") AS product_views,
  COUNTIF(event_type = "add_to_cart") AS add_to_cart,
  COUNTIF(event_type = "checkout_start") AS checkout_started,
  COUNTIF(event_type = "purchase") AS orders_completed,
  SAFE_DIVIDE(COUNTIF(event_type = "add_to_cart"), COUNTIF(event_type = "product_view")) AS view_to_cart_rate,
  SAFE_DIVIDE(COUNTIF(event_type = "checkout_start"), COUNTIF(event_type = "add_to_cart")) AS cart_to_checkout_rate,
  SAFE_DIVIDE(COUNTIF(event_type = "purchase"), COUNTIF(event_type = "checkout_start")) AS checkout_to_purchase_rate
FROM silver.events
GROUP BY DATE(event_timestamp)
'
```

```bash
bq query --use_legacy_sql=false '
CREATE OR REPLACE VIEW gold.monthly_kpis AS
SELECT
  DATE_TRUNC(ordered_at, MONTH) AS month,
  SUM(total_amount) AS total_revenue,
  COUNT(DISTINCT order_id) AS order_count,
  COUNT(DISTINCT customer_id) AS active_customers,
  AVG(total_amount) AS avg_order_value
FROM silver.orders
WHERE status IN ("completed", "delivered")
GROUP BY DATE_TRUNC(ordered_at, MONTH)
'
```

Verificar:
```bash
bq ls gold
bq query --use_legacy_sql=false 'SELECT * FROM gold.conversion_funnel LIMIT 5'
```

---

## Paso 6 — Dry run (estimar costos antes de ejecutar)

> **Buena práctica:** Siempre hacer dry run en queries nuevas antes de lanzarlas en producción.
> **Problema que evitas:** Query que escanea 10 TB y genera un costo de $50 USD en un solo run.

```bash
# Dry run — muestra bytes que va a escanear sin ejecutar
bq query --use_legacy_sql=false --dry_run 'SELECT * FROM silver.orders WHERE DATE(ordered_at) = "2026-02-15"'
```

```bash
# Comparar: query SIN partición (escanea todo)
bq query --use_legacy_sql=false --dry_run 'SELECT * FROM silver.orders'

# vs query CON filtro de partición (escanea solo 1 día)
bq query --use_legacy_sql=false --dry_run 'SELECT * FROM silver.orders WHERE DATE(ordered_at) = "2026-02-15"'
```

> El segundo debería escanear muchos menos bytes. Esa es la ventaja de PARTITION BY.

---

## Paso 7 — Retention policy (GDPR)

> **Buena práctica:** Configurar expiración de datos. Documentar la retention policy en el RAT (Registro de Actividades de Tratamiento).
> **Problema que evitas:** Incumplimiento GDPR por guardar datos más tiempo del declarado — dato auditado.

```bash
# Bronze: retención de 2 años (730 días)
bq update --default_table_expiration 63072000 project-dev-490218:bronze

# Silver: retención de 5 años
bq update --default_table_expiration 157680000 project-dev-490218:silver

# Gold: sin expiración (son vistas, no almacenan datos)
```

Verificar:
```bash
bq show bronze
```

Debe mostrar `Default table expiration ms: 63072000000`

---

## Paso 8 — Row-level Security (filtrar por país/rol)

> **Buena práctica:** Testear la política con un usuario de prueba antes de activarla en producción.
> **Problema que evitas:** Política mal configurada que bloquea acceso a todos o que no filtra nada.

Row-level security filtra filas según quién hace el query. Ejemplo: analistas de MX solo ven datos de MX.

```bash
# Crear política: usuarios con grupo "mx-analysts" solo ven datos de México
bq query --use_legacy_sql=false '
CREATE ROW ACCESS POLICY mexico_only
ON silver.customers
GRANT TO ("group:mx-analysts@tu-dominio.com")
FILTER USING (country = "MX")
'
```

```bash
# Crear política: usuarios con grupo "co-analysts" solo ven datos de Colombia
bq query --use_legacy_sql=false '
CREATE ROW ACCESS POLICY colombia_only
ON silver.customers
GRANT TO ("group:co-analysts@tu-dominio.com")
FILTER USING (country = "CO")
'
```

```bash
# Política para admins: ven todo
bq query --use_legacy_sql=false '
CREATE ROW ACCESS POLICY admin_full_access
ON silver.customers
GRANT TO ("group:data-admins@tu-dominio.com")
FILTER USING (TRUE)
'
```

> **Nota:** Cambiar `@tu-dominio.com` por tu dominio real. Se puede hacer también con `serviceAccount:` para SAs.

---

## Paso 9 — Policy Tags (proteger columnas PII)

> **Buena práctica:** Aplicar Policy Tags en Bronze y Silver — nunca en Gold donde el PII ya está enmascarado.
> **Problema que evitas:** Columna de email en Gold accesible para analistas sin que nadie lo haya autorizado.

### Crear taxonomía y tags

```bash
# Habilitar API de Data Catalog
gcloud services enable datacatalog.googleapis.com

# Crear taxonomía
gcloud data-catalog taxonomies create \
  --display-name="PII Classification" \
  --description="Clasificación de datos personales" \
  --location=eu
```

Después desde la consola (console.cloud.google.com → Data Catalog → Policy Tags):

1. Abrir la taxonomía "PII Classification"
2. Crear tags:
   - `high_sensitivity` → email, phone, address (requiere aprobación para acceder)
   - `medium_sensitivity` → name, city, country
   - `low_sensitivity` → customer_segment, order_count

### Aplicar tags a columnas

Desde la consola: BigQuery → silver.customers → Schema → click en columna `email` → Edit → Agregar Policy Tag `high_sensitivity`

Columnas a proteger:

| Tabla | Columna | Tag |
|---|---|---|
| silver.customers | email | high_sensitivity |
| silver.customers | phone | high_sensitivity |
| silver.customers | address | high_sensitivity |
| silver.customers | first_name | medium_sensitivity |
| silver.customers | last_name | medium_sensitivity |
| silver.payments | payment_method | high_sensitivity |
| bronze.* | raw_data | high_sensitivity (contiene PII en JSON) |

---

## Paso 10 — Permisos IAM de BigQuery

Agregar roles de BigQuery a las SA en `infra/iam.tf` y hacer push:

| SA | Rol | Para qué |
|---|---|---|
| `sa-pipeline` | `roles/bigquery.admin` | Crear datasets/tablas via Terraform |
| `sa-cloudrun` | `roles/bigquery.dataEditor` | Insertar datos (Bronze) |
| `sa-functions` | `roles/bigquery.dataEditor` | Transformar datos (Silver, Gold) |
| `sa-monitoring` | `roles/bigquery.dataViewer` | Leer datos para dashboards |

---

## Paso 11 — Definir en Terraform

Crear `infra/bigquery.tf` con datasets, tablas y vistas para que el pipeline los administre.

> **Las transformaciones Bronze → Silver NO se hacen con queries manuales en producción.**
> Se orquestan con **Cloud Composer (Airflow)** que programa y ejecuta los ETLs automáticamente.
> Eso se configura en el módulo de orquestación (Hora 8).

---

## Checklist

- [ ] API habilitada
- [ ] 3 datasets creados en región EU
- [ ] 8 tablas Bronze con esquema explícito
- [ ] 8 tablas Silver con PARTITION y CLUSTER
- [ ] 5 vistas Gold (no tablas)
- [ ] Dry run probado
- [ ] Retention policy configurada (Bronze 2 años, Silver 5 años)
- [ ] Row-level security configurada
- [ ] Policy Tags aplicados a columnas PII
- [ ] Permisos IAM agregados
- [ ] Definido en Terraform
