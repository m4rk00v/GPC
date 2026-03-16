# Pub/Sub + Cloud Storage → BigQuery Bronze (E-commerce)

## Qué es Pub/Sub

Sistema de mensajería asíncrona de GCP. Un servicio **publica** un mensaje y otro lo **consume**, sin que se conozcan entre sí.

| Aspecto | Pub/Sub | Análogo AWS |
|---|---|---|
| Qué es | Mensajería asíncrona | SNS + SQS |
| Modelo | Publish/Subscribe | Publish/Subscribe |
| Garantía | At-least-once delivery | At-least-once |
| Escala | Automática (millones de msgs/seg) | Automática |
| Retención | Hasta 31 días | 14 días (SQS) |
| Dead Letter Queue | Sí (configurable) | Sí (DLQ en SQS) |

## Conceptos clave

```
┌──────────┐     ┌─────────┐     ┌──────────────┐
│ Publisher │────▶│  Topic  │────▶│ Subscription │────▶ Subscriber
└──────────┘     └─────────┘     └──────────────┘

- Publisher: quien envía el mensaje (Cloud Storage, tu app, etc.)
- Topic: canal donde llegan los mensajes (como un buzón)
- Subscription: la conexión entre el topic y quien consume
- Subscriber: quien recibe y procesa el mensaje (Cloud Function, Dataflow, etc.)
```

| Concepto | Análogo | Ejemplo en este proyecto |
|---|---|---|
| **Topic** | Canal de Slack | `csv-uploaded` — avisa que hay un CSV nuevo |
| **Subscription** | Persona suscrita al canal | Cloud Function que escucha el topic |
| **Message** | Mensaje en el canal | `{bucket: "...", name: "customers/data.csv"}` |
| **Ack** | "Leído" en el mensaje | Function confirma que procesó el CSV |
| **Dead Letter Topic** | Canal de errores | Mensajes que fallaron 5+ veces van aquí |

---

## Flujo completo: CSV → Bronze

```
1. Subes un CSV a Cloud Storage (bucket)
         │
         ▼
2. Cloud Storage dispara notificación → Pub/Sub topic "csv-uploaded"
         │
         ▼
3. Pub/Sub entrega el mensaje a la subscription
         │
         ▼
4. Cloud Function (subscriber) se activa automáticamente
         │
         ▼
5. Function lee el CSV del bucket, parsea las filas
         │
         ▼
6. Inserta en BigQuery Bronze como JSON crudo
         │
         ▼
7. Function hace ACK → Pub/Sub marca el mensaje como procesado
         │
         ▼
8. Si falla → Pub/Sub reintenta (hasta 5 veces) → Dead Letter Topic
```

### Por qué este flujo y no insertar directo

| Insertar directo con `bq query` | Con Pub/Sub + Cloud Function |
|---|---|
| Manual, no escala | Automático, escala solo |
| No hay registro de qué se procesó | Pub/Sub guarda el mensaje hasta que se confirma |
| Si falla, no te enteras | Si falla, Pub/Sub reintenta automáticamente |
| No hay separación de responsabilidades | Cada componente hace una sola cosa |
| No hay Dead Letter Queue | Mensajes que fallan van a DLQ para análisis |

---

## Arquitectura

```
                    ┌─────────────────────┐
                    │   Cloud Storage     │
                    │   bucket:           │
                    │   project-dev-      │
                    │   490218-ecommerce- │
                    │   raw-data          │
                    │                     │
                    │   /customers/       │
                    │   /products/        │
                    │   /orders/          │
                    │   /order_items/     │
                    │   /payments/        │
                    │   /events/          │
                    │   /inventory/       │
                    │   /reviews/         │
                    └──────────┬──────────┘
                               │ OBJECT_FINALIZE (archivo creado)
                               ▼
                    ┌─────────────────────┐
                    │      Pub/Sub        │
                    │                     │
                    │  Topic:             │
                    │  csv-uploaded       │
                    │                     │
                    │  Subscription:      │
                    │  csv-uploaded-sub   │
                    │  (push a Function)  │
                    │                     │
                    │  Dead Letter Topic: │
                    │  csv-uploaded-dlq   │
                    └──────────┬──────────┘
                               │ Push
                               ▼
                    ┌─────────────────────┐
                    │   Cloud Function    │
                    │   "ingest-csv"      │
                    │                     │
                    │   1. Recibe msg     │
                    │   2. Valida .csv    │
                    │   3. Detecta tabla  │
                    │      por carpeta    │
                    │   4. Lee CSV de GCS │
                    │   5. Parsea filas   │
                    │   6. Inserta Bronze │
                    │   7. ACK a Pub/Sub  │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │    BigQuery Bronze   │
                    │                     │
                    │  customers_raw      │
                    │  products_raw       │
                    │  orders_raw         │
                    │  order_items_raw    │
                    │  payments_raw       │
                    │  events_raw         │
                    │  inventory_raw      │
                    │  reviews_raw        │
                    └─────────────────────┘
```

### Cómo sabe la Function en qué tabla insertar

Por la **carpeta** del bucket:

| Archivo subido a | Se inserta en |
|---|---|
| `gs://.../customers/*.csv` | `bronze.customers_raw` |
| `gs://.../products/*.csv` | `bronze.products_raw` |
| `gs://.../orders/*.csv` | `bronze.orders_raw` |
| `gs://.../order_items/*.csv` | `bronze.order_items_raw` |
| `gs://.../payments/*.csv` | `bronze.payments_raw` |
| `gs://.../events/*.csv` | `bronze.events_raw` |
| `gs://.../inventory/*.csv` | `bronze.inventory_raw` |
| `gs://.../reviews/*.csv` | `bronze.reviews_raw` |

---

## Implementación paso a paso

> **EN PRODUCCIÓN:** Los pasos 1 a 6 (APIs, bucket, Pub/Sub, notificación, Cloud Function)
> se definen en Terraform (`infra/storage.tf`, `infra/pubsub.tf`, `infra/functions.tf`).
> Los comandos `gcloud`/`gsutil` de abajo son para **entender qué hace cada paso**.
> Solo los pasos 7-10 (generar CSVs, subirlos, verificar) se ejecutan manualmente.

### Paso 1 — Habilitar APIs (Terraform: `infra/main.tf`)

```bash
gcloud services enable pubsub.googleapis.com
gcloud services enable cloudfunctions.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable storage.googleapis.com
gcloud services enable eventarc.googleapis.com
gcloud services enable run.googleapis.com
```

Verificar:
```bash
gcloud services list --enabled | grep -E "pubsub|functions|storage|eventarc"
```

> **Buena práctica:** En producción estas APIs se habilitan con Terraform, no manualmente.
> No lo hacemos aquí porque `sa-pipeline` no tiene `serviceusage.services.list`.

---

### Paso 2 — Crear el bucket de Cloud Storage (Terraform: `infra/storage.tf`)

> **Buena práctica:** Nombre del bucket con project-id como prefijo para evitar colisiones globales.
> Los nombres de bucket son **únicos globalmente** en todo GCP.

> **Buena práctica:** Ubicación EU para GDPR — igual que BigQuery.
> **Problema que evitas:** Datos en US que luego se transfieren a EU — violación de GDPR.

```bash
gsutil mb -l EU "gs://project-dev-490218-ecommerce-raw-data"
```

Crear las carpetas (una por entidad):

```bash
for folder in customers products orders order_items payments events inventory reviews; do
  echo "" | gsutil cp - "gs://project-dev-490218-ecommerce-raw-data/${folder}/.keep"
done
```

> **Nota:** Cloud Storage no tiene carpetas reales — son prefijos en el nombre del archivo.
> El `.keep` es un archivo vacío para que la "carpeta" aparezca en la consola.

Verificar:
```bash
gsutil ls "gs://project-dev-490218-ecommerce-raw-data/"
```

Debe mostrar 8 carpetas.

---

### Paso 3 — Crear el topic de Pub/Sub + Dead Letter Topic (Terraform: `infra/pubsub.tf`)

> **Buena práctica:** Siempre crear un Dead Letter Topic (DLQ).
> **Problema que evitas:** Mensajes que fallan indefinidamente, consumen reintentos y no te enteras.

```bash
# Topic principal — recibe notificaciones de Cloud Storage
gcloud pubsub topics create csv-uploaded
```

```bash
# Dead Letter Topic — recibe mensajes que fallaron 5+ veces
gcloud pubsub topics create csv-uploaded-dlq
```

```bash
# Subscription del DLQ para poder leer los mensajes fallidos
gcloud pubsub subscriptions create csv-uploaded-dlq-sub \
  --topic=csv-uploaded-dlq \
  --ack-deadline=60 \
  --message-retention-duration=7d
```

Verificar:
```bash
gcloud pubsub topics list
gcloud pubsub subscriptions list
```

> **Buena práctica:** `message-retention-duration=7d` en el DLQ para tener tiempo de investigar errores.
> En el topic principal, Pub/Sub retiene mensajes 7 días por defecto (configurable hasta 31).

---

### Paso 4 — Configurar notificación de Cloud Storage → Pub/Sub (Terraform: `infra/pubsub.tf`)

> **`OBJECT_FINALIZE`** se dispara cuando un archivo **se termina de subir** al bucket.
> No se dispara con archivos parciales o escrituras incompletas.

```bash
gsutil notification create \
  -t csv-uploaded \
  -f json \
  -e OBJECT_FINALIZE \
  "gs://project-dev-490218-ecommerce-raw-data"
```

Verificar:
```bash
gsutil notification list "gs://project-dev-490218-ecommerce-raw-data"
```

> **Buena práctica:** Usar `-f json` para que el mensaje incluya metadatos completos (bucket, nombre, tamaño, tipo).
> **Buena práctica:** Solo `OBJECT_FINALIZE` — no `OBJECT_DELETE` ni `OBJECT_ARCHIVE` que generarían ruido.

---

### Paso 5 — Crear la Cloud Function (ingestor) (Terraform: `infra/functions.tf`)

> **Buena práctica:** Una function por responsabilidad. Esta solo hace: leer CSV → insertar en Bronze.
> **Buena práctica:** Usar Gen2 (Cloud Run bajo el capó) — más performante y configurable que Gen1.
> **Buena práctica:** Service Account dedicada (`sa-functions`) — nunca usar la SA por defecto.

El código está en `pub-sub/ingestor/`:

```
pub-sub/ingestor/
├── main.py              ← lógica de la function
└── requirements.txt     ← dependencias
```

**`ingestor/main.py`** — ya creado con:
- Mapeo carpeta → tabla Bronze
- Validación de archivos (solo .csv)
- Parsing de CSV a JSON para Bronze
- Esquema diferenciado para events (event_id, event_type, raw_payload) vs resto (record_id, raw_data)
- Logging de errores y éxito

**`ingestor/requirements.txt`:**
```
google-cloud-bigquery>=3.0.0
google-cloud-storage>=2.0.0
```

---

### Paso 6 — Deploy de la Cloud Function (Terraform: `infra/functions.tf`)

> **Buena práctica:** `--gen2` usa Cloud Run internamente — mejor cold start y concurrencia.
> **Buena práctica:** `--memory=512MB` — CSVs grandes pueden necesitar más memoria para parsear.
> **Buena práctica:** `--timeout=300s` — CSVs de 100K+ filas pueden tardar más de 2 minutos.
> **Buena práctica:** `--max-instances=5` — limitar instancias para no sobrecargar BigQuery con inserts concurrentes.
> **Buena práctica:** `--min-instances=0` — no pagar por instancias idle. El cold start es aceptable para batch.

```bash
cd /Users/appleuser/Desktop/GPC/pub-sub/ingestor

gcloud functions deploy ingest-csv \
  --gen2 \
  --runtime=python312 \
  --region=europe-west1 \
  --source=. \
  --entry-point=ingest_csv \
  --trigger-topic=csv-uploaded \
  --service-account=sa-functions@project-dev-490218.iam.gserviceaccount.com \
  --memory=512MB \
  --timeout=300s \
  --max-instances=5 \
  --min-instances=0 \
  --set-env-vars=GCP_PROJECT=project-dev-490218
```

> **Buena práctica:** `--region=europe-west1` — misma región que el bucket y BigQuery (EU).
> **Problema que evitas:** Latencia y costos de transferencia entre regiones.

Verificar:
```bash
gcloud functions describe ingest-csv --region=europe-west1 --gen2
```

---

### Paso 7 — Generar CSVs de prueba (manual — datos de prueba)

Hay un script que genera datos ficticios realistas:

```bash
cd /Users/appleuser/Desktop/GPC/pub-sub/sample-data
python generate.py
```

Genera:

| CSV | Registros | Descripción |
|---|---|---|
| `customers.csv` | 50 | Clientes de MX, CO, AR, CL, PE, ES |
| `products.csv` | 20 | Electronics, Clothing, Home |
| `orders.csv` | 100 | Estados variados, fechas, envíos |
| `order_items.csv` | ~200 | 1-4 items por orden con descuentos |
| `payments.csv` | ~90 | Tarjeta, PayPal, crypto |
| `events.csv` | 500 | Clickstream: page_view, search, add_to_cart, purchase |
| `inventory.csv` | ~40 | 3 warehouses (EU west, EU east, LATAM) |
| `reviews.csv` | 30 | Ratings 1-5 con comentarios |

Verificar que se generaron:
```bash
ls -la *.csv
wc -l *.csv
```

---

### Paso 8 — Subir CSVs al bucket (manual — dispara el pipeline)

> **Importante:** Cada `gsutil cp` dispara un evento `OBJECT_FINALIZE` → Pub/Sub → Cloud Function → BigQuery.
> Los 8 archivos se procesan en paralelo automáticamente.

```bash
cd /Users/appleuser/Desktop/GPC/pub-sub/sample-data

gsutil cp customers.csv "gs://project-dev-490218-ecommerce-raw-data/customers/"
gsutil cp products.csv "gs://project-dev-490218-ecommerce-raw-data/products/"
gsutil cp orders.csv "gs://project-dev-490218-ecommerce-raw-data/orders/"
gsutil cp order_items.csv "gs://project-dev-490218-ecommerce-raw-data/order_items/"
gsutil cp payments.csv "gs://project-dev-490218-ecommerce-raw-data/payments/"
gsutil cp events.csv "gs://project-dev-490218-ecommerce-raw-data/events/"
gsutil cp inventory.csv "gs://project-dev-490218-ecommerce-raw-data/inventory/"
gsutil cp reviews.csv "gs://project-dev-490218-ecommerce-raw-data/reviews/"
```

---

### Paso 9 — Verificar que llegaron a Bronze (manual — validación)

Espera ~30-60 segundos para que las Functions procesen:

```bash
# Verificar conteos en cada tabla
bq query --use_legacy_sql=false 'SELECT "customers" as table_name, COUNT(*) as rows FROM bronze.customers_raw UNION ALL SELECT "products", COUNT(*) FROM bronze.products_raw UNION ALL SELECT "orders", COUNT(*) FROM bronze.orders_raw UNION ALL SELECT "order_items", COUNT(*) FROM bronze.order_items_raw UNION ALL SELECT "payments", COUNT(*) FROM bronze.payments_raw UNION ALL SELECT "events", COUNT(*) FROM bronze.events_raw UNION ALL SELECT "inventory", COUNT(*) FROM bronze.inventory_raw UNION ALL SELECT "reviews", COUNT(*) FROM bronze.reviews_raw'
```

Ver los logs de la función:

```bash
gcloud functions logs read ingest-csv --region=europe-west1 --limit=30 --gen2
```

> **Buena práctica:** Siempre verificar logs después del primer deploy.
> Buscar: "Insertadas X filas en bronze.XXX" para cada tabla.

### Si algo falló:

```bash
# Ver mensajes en el Dead Letter Topic
gcloud pubsub subscriptions pull csv-uploaded-dlq-sub --limit=10 --auto-ack
```

---

### Paso 10 — Verificar un registro completo (manual — validación)

```bash
# Ver cómo se almacena un customer en Bronze (JSON crudo)
bq query --use_legacy_sql=false 'SELECT * FROM bronze.customers_raw LIMIT 1'
```

Debe verse así:
```
record_id  | raw_data                                           | source                    | ingested_at
cust-0001  | {"id":"cust-0001","email":"maria.garcia42@..."}   | gcs/customers/customers.. | 2026-03-15 ...
```

> El dato crudo se guarda como JSON en `raw_data`. Bronze **nunca parsea** — solo almacena.
> El parseo se hace en la transformación Bronze → Silver (Cloud Composer / Airflow).

---

## Buenas prácticas resumen

| Práctica | Por qué | Problema que evitas |
|---|---|---|
| Dead Letter Topic (DLQ) | Captura mensajes que fallan repetidamente | Mensajes perdidos sin diagnóstico |
| `OBJECT_FINALIZE` solo | Solo procesa archivos completos | Procesar archivos parciales o borrados |
| Gen2 Functions | Mejor performance, concurrencia nativa | Cold starts largos de Gen1 |
| SA dedicada (`sa-functions`) | Principio de menor privilegio | Function con permisos de admin |
| `--max-instances=5` | Limitar concurrencia | 100 CSVs simultáneos saturan BigQuery |
| Región EU consistente | Bucket, Function, BigQuery en EU | Transferencia cross-region y GDPR |
| Esquema explícito en Bronze | Tipos correctos desde el inicio | BigQuery infiere STRING para todo |
| `message-retention-duration=7d` en DLQ | Tiempo para investigar errores | Mensajes fallidos desaparecen antes de debug |
| Idempotencia | Si se reprocesa un CSV, no duplica datos | Datos duplicados en Bronze |
| JSON crudo en Bronze | No perder información del origen | Campos descartados que después necesitas |

---

## Streaming (tiempo real) vs Batch (CSVs)

Este flujo es para **batch** (cargas de archivos). Para **streaming** (tiempo real):

```
App (Cloud Run) → Pub/Sub topic "events" → Dataflow → BigQuery Bronze
```

| Tipo | Cuándo | Latencia | Ejemplo E-commerce |
|---|---|---|---|
| **Batch (este flujo)** | Cargas programadas | Minutos | Catálogo, dump de usuarios, CSVs de proveedores |
| **Streaming** | Eventos en tiempo real | Segundos | Clicks, búsquedas, add_to_cart, compras |

Ambos escriben en Bronze. Las transformaciones Bronze → Silver → Gold las orquesta **Cloud Composer (Airflow)**.

---

## Permisos necesarios (ya configurados)

| SA | Rol | Para qué | Estado |
|---|---|---|---|
| `sa-functions` | `roles/bigquery.dataEditor` | Insertar en Bronze | Ya en iam.tf |
| `sa-functions` | `roles/storage.objectViewer` | Leer CSVs del bucket | Ya en iam.tf |
| `sa-functions` | `roles/secretmanager.secretAccessor` | Leer secretos (si necesita) | Ya en iam.tf |
| `sa-pubsub` | `roles/pubsub.publisher` | Publicar mensajes | Ya en iam.tf |
| `sa-pubsub` | `roles/pubsub.subscriber` | Consumir mensajes | Ya en iam.tf |

> **Buena práctica:** Verificar que `sa-functions` tiene acceso al bucket específico, no a todos los buckets.
> En producción, se configura IAM a nivel de bucket, no de proyecto.

---

## Terraform

> **EN PRODUCCIÓN:** Todo esto se define en Terraform, no manualmente.

| Recurso | Resource Terraform | Archivo |
|---|---|---|
| Bucket | `google_storage_bucket` | `infra/storage.tf` |
| Pub/Sub topic | `google_pubsub_topic` | `infra/pubsub.tf` |
| Pub/Sub DLQ topic | `google_pubsub_topic` | `infra/pubsub.tf` |
| Pub/Sub subscription | `google_pubsub_subscription` | `infra/pubsub.tf` |
| Notificación GCS→Pub/Sub | `google_storage_notification` | `infra/pubsub.tf` |
| Cloud Function | `google_cloudfunctions2_function` | `infra/functions.tf` |

---

## Errores comunes

| Error | Causa | Solución |
|---|---|---|
| Function no se activa | Notificación GCS→Pub/Sub no configurada | `gsutil notification list` para verificar |
| `PERMISSION_DENIED` en BigQuery | `sa-functions` sin `bigquery.dataEditor` | Verificar roles en `iam.tf` |
| `PERMISSION_DENIED` en Storage | `sa-functions` sin `storage.objectViewer` | Agregar rol |
| Datos duplicados en Bronze | CSV subido dos veces | Implementar idempotencia con `record_id` |
| Function timeout | CSV muy grande (>100K filas) | Aumentar `--timeout` o partir el CSV |
| Message en DLQ | Function crasheó 5+ veces | Revisar logs: `gcloud functions logs read` |
| `No module named 'google.cloud'` | `requirements.txt` mal escrito | Verificar que tiene `google-cloud-bigquery` |

---

## Checklist

- [ ] APIs habilitadas (pubsub, functions, storage, eventarc, run)
- [ ] Bucket creado en EU con 8 carpetas
- [ ] Pub/Sub topic `csv-uploaded` creado
- [ ] Pub/Sub DLQ topic `csv-uploaded-dlq` creado
- [ ] Notificación GCS → Pub/Sub configurada (OBJECT_FINALIZE)
- [ ] Cloud Function `ingest-csv` deployada (Gen2, europe-west1)
- [ ] CSVs generados con `generate.py`
- [ ] CSVs subidos al bucket
- [ ] Datos verificados en Bronze (conteos correctos)
- [ ] Logs revisados sin errores
- [ ] Definido en Terraform
