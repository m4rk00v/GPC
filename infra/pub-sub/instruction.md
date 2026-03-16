# Pub/Sub — Configuración de Publishers, Subscribers, Eventos y Monitoreo

## 1. Publishers (quién envía mensajes)

### 1.1 Cloud Storage → Pub/Sub (notificación automática)

Ya configurado en `pubsub.tf`. Cuando un CSV sube al bucket, GCS publica un mensaje automáticamente.

**Verificar desde consola GCP:**
1. Console → **Cloud Storage** → click en el bucket `project-dev-490218-ecommerce-raw-data`
2. Pestaña **Notifications** → debe aparecer el topic `csv-uploaded`

**Verificar desde CLI:**
```bash
gsutil notification list "gs://project-dev-490218-ecommerce-raw-data"
```

### 1.2 Publisher manual (desde la app o testing)

Para publicar un mensaje manualmente (simular que un CSV se subió):

```bash
gcloud pubsub topics publish csv-uploaded \
  --message='{"bucket":"project-dev-490218-ecommerce-raw-data","name":"customers/test.csv","size":"1024","contentType":"text/csv"}'
```

> **Uso:** Testing, debugging, o simular eventos sin subir archivos reales.

### 1.3 Publisher desde código (Cloud Run / App)

Si tu app necesita publicar eventos directamente al topic:

```python
from google.cloud import pubsub_v1
import json

publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path("project-dev-490218", "csv-uploaded")

message = json.dumps({
    "bucket": "project-dev-490218-ecommerce-raw-data",
    "name": "orders/new-orders-2026-03.csv",
}).encode("utf-8")

future = publisher.publish(topic_path, message)
print(f"Mensaje publicado: {future.result()}")
```

> **SA necesaria:** `sa-cloudrun` ya tiene `roles/pubsub.publisher`.

---

## 2. Subscribers (quién recibe mensajes)

### 2.1 Tipos de subscription

| Tipo | Cómo funciona | Cuándo usar |
|---|---|---|
| **Push** | Pub/Sub envía el mensaje a un endpoint HTTP | Cloud Functions, Cloud Run (lo que usamos) |
| **Pull** | El subscriber pide mensajes cuando quiere | Workers, batch processing, debugging |
| **BigQuery** | Pub/Sub escribe directo a BigQuery | Streaming sin intermediarios |

### 2.2 Push subscription (Cloud Function — ya configurado)

La Cloud Function `ingest-csv` recibe mensajes automáticamente via Eventarc trigger.

**Verificar desde consola GCP:**
1. Console → **Pub/Sub** → **Subscriptions**
2. Buscar la subscription creada por Eventarc (nombre auto-generado)
3. Click → ver **Delivery type: Push**, **Endpoint: URL de la Function**

**Verificar desde CLI:**
```bash
gcloud pubsub subscriptions list --filter="topic:csv-uploaded"
```

### 2.3 Pull subscription (para debugging / monitoreo manual)

Crear una subscription pull adicional para leer mensajes manualmente:

```bash
# Crear subscription pull (no interfiere con la push de la Function)
gcloud pubsub subscriptions create csv-uploaded-debug \
  --topic=csv-uploaded \
  --ack-deadline=60 \
  --message-retention-duration=1d \
  --expiration-period=7d
```

> **Importante:** Un topic puede tener múltiples subscriptions.
> Cada subscription recibe una **copia** del mensaje. No compiten entre sí.

```bash
# Leer mensajes (sin ACK — se pueden volver a leer)
gcloud pubsub subscriptions pull csv-uploaded-debug --limit=5

# Leer mensajes con ACK (se eliminan después de leer)
gcloud pubsub subscriptions pull csv-uploaded-debug --limit=5 --auto-ack
```

> **Uso:** Verificar qué mensajes llegan al topic sin afectar la Cloud Function.

### 2.4 Subscription a BigQuery (streaming directo)

Para datos de streaming (eventos en tiempo real), se puede configurar Pub/Sub para que escriba directamente en BigQuery sin Cloud Function:

```bash
gcloud pubsub subscriptions create events-to-bigquery \
  --topic=realtime-events \
  --bigquery-table=project-dev-490218:bronze.events_raw \
  --use-topic-schema
```

> **Nota:** Esto es para el flujo de streaming futuro, no para el batch de CSVs.

---

## 3. Configuración de eventos

### 3.1 Eventos de Cloud Storage

| Evento | Cuándo se dispara | Configurado |
|---|---|---|
| `OBJECT_FINALIZE` | Archivo termina de subir | Sí (el que usamos) |
| `OBJECT_METADATA_UPDATE` | Metadatos del archivo cambian | No |
| `OBJECT_DELETE` | Archivo se borra | No |
| `OBJECT_ARCHIVE` | Archivo se archiva (versionado) | No |

> **Buena práctica:** Solo `OBJECT_FINALIZE`. Los otros generan ruido y la Function
> los descartaría igualmente.

### 3.2 Filtros de eventos

Si quieres que solo ciertos archivos disparen el evento (ej: solo CSVs, no imágenes):

```bash
# Filtrar por prefijo (solo carpeta customers/)
gsutil notification create \
  -t csv-uploaded \
  -f json \
  -e OBJECT_FINALIZE \
  -p "customers/" \
  "gs://project-dev-490218-ecommerce-raw-data"
```

> **En nuestro caso:** No filtramos por prefijo porque la Function ya valida
> el archivo (.csv) y la carpeta (customers/, products/, etc.).

### 3.3 Formato del mensaje

Cuando GCS notifica a Pub/Sub, el mensaje tiene esta estructura:

```json
{
  "kind": "storage#object",
  "id": "project-dev-490218-ecommerce-raw-data/customers/customers.csv/1710532800000000",
  "selfLink": "https://www.googleapis.com/storage/v1/b/...",
  "name": "customers/customers.csv",
  "bucket": "project-dev-490218-ecommerce-raw-data",
  "generation": "1710532800000000",
  "metageneration": "1",
  "contentType": "text/csv",
  "timeCreated": "2026-03-16T10:00:00.000Z",
  "updated": "2026-03-16T10:00:00.000Z",
  "size": "4096",
  "md5Hash": "abc123...",
  "crc32c": "xyz789..."
}
```

La Function usa `name` (para detectar carpeta/tabla) y `bucket` (para leer el archivo).

### 3.4 Atributos del mensaje

Pub/Sub también recibe atributos junto con el mensaje:

| Atributo | Valor | Para qué |
|---|---|---|
| `bucketId` | `project-dev-490218-ecommerce-raw-data` | Identificar el bucket |
| `objectId` | `customers/customers.csv` | Path del archivo |
| `eventType` | `OBJECT_FINALIZE` | Tipo de evento |
| `notificationConfig` | `projects/_/buckets/.../notificationConfigs/1` | ID de la notificación |

---

## 4. Dead Letter Queue (DLQ)

### 4.1 Configuración

Ya creado en `pubsub.tf`:
- Topic: `csv-uploaded-dlq`
- Subscription: `csv-uploaded-dlq-sub` (pull, retención 7 días)

### 4.2 Cuándo llega un mensaje al DLQ

1. La Function recibe el mensaje
2. La Function falla (excepción, timeout, error de BigQuery)
3. Pub/Sub reintenta automáticamente (backoff exponencial)
4. Después de **5 intentos fallidos** → mensaje va al DLQ

### 4.3 Leer mensajes del DLQ

```bash
# Ver cuántos mensajes hay en el DLQ
gcloud pubsub subscriptions describe csv-uploaded-dlq-sub --format="value(numUndeliveredMessages)"

# Leer los mensajes fallidos
gcloud pubsub subscriptions pull csv-uploaded-dlq-sub --limit=10

# Leer y eliminar (después de investigar)
gcloud pubsub subscriptions pull csv-uploaded-dlq-sub --limit=10 --auto-ack
```

### 4.4 Reprocesar mensajes del DLQ

Si el error fue temporal (BigQuery caído, permiso faltante) y ya se arregló:

```bash
# Leer mensaje del DLQ, publicarlo de nuevo en el topic principal
gcloud pubsub subscriptions pull csv-uploaded-dlq-sub --limit=1 --format=json | \
  jq -r '.[0].message.data' | \
  base64 --decode | \
  gcloud pubsub topics publish csv-uploaded --message=-
```

---

## 5. Monitoreo desde la consola GCP

### 5.1 Pub/Sub — Dashboard

1. Console → **Pub/Sub** → **Topics**
2. Click en `csv-uploaded`
3. Pestaña **Monitoring** → verás:

| Métrica | Qué muestra |
|---|---|
| **Publish message count** | Cuántos mensajes se publicaron (CSVs subidos) |
| **Publish message size** | Tamaño de los mensajes |
| **Subscription pull/push count** | Cuántos mensajes entregó a subscribers |
| **Unacked message count** | Mensajes pendientes de procesar |
| **Oldest unacked message age** | Hace cuánto está el mensaje más viejo sin procesar |

> **Alerta recomendada:** Si `oldest unacked message age` > 5 minutos, algo está mal.

### 5.2 Cloud Functions — Logs y métricas

1. Console → **Cloud Functions** → click en `ingest-csv`
2. Pestaña **Logs** → ver ejecuciones:
   - `[OK] Insertadas 50 filas en bronze.customers_raw` → éxito
   - `[ERROR] Fallo insertando...` → fallo
   - `[SKIP] Ignorando .keep` → archivo ignorado

3. Pestaña **Metrics** → verás:

| Métrica | Qué muestra |
|---|---|
| **Invocations** | Cuántas veces se ejecutó |
| **Execution time** | Cuánto tardó cada ejecución |
| **Memory usage** | Cuánta memoria usó (vs 512MB asignados) |
| **Error count** | Cuántas ejecuciones fallaron |
| **Instance count** | Cuántas instancias activas (vs max 5) |

> **Alerta recomendada:** Si `error count` > 0 por más de 10 minutos.

### 5.3 Cloud Storage — Actividad

1. Console → **Cloud Storage** → click en el bucket
2. Pestaña **Objects** → ver archivos subidos
3. Click en un archivo → **View metadata** → ver fecha, tamaño, tipo

### 5.4 BigQuery — Verificar datos

1. Console → **BigQuery** → **SQL Workspace**
2. En el editor SQL:

```sql
-- Cuántos registros por tabla Bronze
SELECT 'customers' as tabla, COUNT(*) as filas FROM bronze.customers_raw
UNION ALL SELECT 'products', COUNT(*) FROM bronze.products_raw
UNION ALL SELECT 'orders', COUNT(*) FROM bronze.orders_raw
UNION ALL SELECT 'events', COUNT(*) FROM bronze.events_raw
ORDER BY tabla
```

```sql
-- Últimos registros ingestados
SELECT * FROM bronze.customers_raw
ORDER BY ingested_at DESC
LIMIT 5
```

```sql
-- Verificar fuentes de ingesta
SELECT source, COUNT(*) as registros
FROM bronze.customers_raw
GROUP BY source
```

### 5.5 Cloud Logging — Logs centralizados

1. Console → **Logging** → **Logs Explorer**
2. Query para ver todo el flujo de un CSV:

```
resource.type="cloud_function"
resource.labels.function_name="ingest-csv"
severity>=INFO
```

3. Query para ver solo errores:

```
resource.type="cloud_function"
resource.labels.function_name="ingest-csv"
severity>=ERROR
```

4. Query para ver eventos de Pub/Sub:

```
resource.type="pubsub_topic"
resource.labels.topic_id="csv-uploaded"
```

---

## 6. Alertas recomendadas

Configurar en Console → **Monitoring** → **Alerting** → **Create Policy**:

| Alerta | Condición | Notificación |
|---|---|---|
| Function fallando | Error count > 0 por 10 min | Email / Slack |
| Mensajes acumulados | Unacked messages > 100 por 5 min | Email / Slack |
| DLQ con mensajes | DLQ message count > 0 | Email / Slack (urgente) |
| Function lenta | Execution time p95 > 120s | Email |
| Function sin memoria | Memory usage > 80% | Email |

### Crear alerta desde CLI (ejemplo: DLQ con mensajes)

```bash
gcloud monitoring policies create --policy-from-file=- <<'EOF'
{
  "displayName": "Pub/Sub DLQ has messages",
  "conditions": [{
    "displayName": "DLQ message count > 0",
    "conditionThreshold": {
      "filter": "resource.type=\"pubsub_subscription\" AND resource.labels.subscription_id=\"csv-uploaded-dlq-sub\" AND metric.type=\"pubsub.googleapis.com/subscription/num_undelivered_messages\"",
      "comparison": "COMPARISON_GT",
      "thresholdValue": 0,
      "duration": "300s"
    }
  }],
  "combiner": "OR",
  "notificationChannels": []
}
EOF
```

> **Nota:** Agregar `notificationChannels` con el ID del canal de notificación
> (email, Slack, PagerDuty). Configurar en Monitoring → Notification channels.

---

## 7. Troubleshooting

### El CSV se subió pero no aparece en Bronze

```bash
# 1. Verificar que la notificación está configurada
gsutil notification list "gs://project-dev-490218-ecommerce-raw-data"

# 2. Verificar que el topic tiene mensajes
gcloud pubsub subscriptions pull csv-uploaded-debug --limit=5

# 3. Verificar logs de la Function
gcloud functions logs read ingest-csv --region=europe-west1 --limit=20 --gen2

# 4. Verificar que la Function existe y está activa
gcloud functions describe ingest-csv --region=europe-west1 --gen2 --format="value(state)"
```

### La Function falla repetidamente

```bash
# 1. Ver el error específico
gcloud functions logs read ingest-csv --region=europe-west1 --limit=5 --gen2 --severity=ERROR

# 2. Verificar permisos de sa-functions
gcloud projects get-iam-policy project-dev-490218 \
  --flatten="bindings[].members" \
  --filter="bindings.members:sa-functions@" \
  --format="table(bindings.role)"

# 3. Verificar que las tablas Bronze existen
bq ls bronze

# 4. Ver mensajes en el DLQ
gcloud pubsub subscriptions pull csv-uploaded-dlq-sub --limit=5
```

### Datos duplicados en Bronze

```bash
# Ver si hay duplicados por source (mismo archivo procesado 2 veces)
bq query --use_legacy_sql=false '
SELECT source, COUNT(*) as veces
FROM bronze.customers_raw
GROUP BY source
HAVING COUNT(*) > 1
'
```

> **Solución:** Implementar idempotencia — antes de insertar, verificar si el `source`
> ya fue procesado. O usar una tabla de control `bronze._ingestion_log`.
