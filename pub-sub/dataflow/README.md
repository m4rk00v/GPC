# Dataflow — Streaming de ClickEvents en tiempo real

## Qué es Dataflow

Dataflow es el servicio de GCP que ejecuta **Apache Beam** — un framework para procesar datos tanto en batch (lotes) como en streaming (continuo). Dataflow administra los workers (VMs), el auto-scaling y la tolerancia a fallos.

| Aspecto | Dataflow | Análogo AWS |
|---|---|---|
| Qué es | Motor de procesamiento managed | Amazon Kinesis Data Analytics |
| Framework | Apache Beam (Python / Java) | Apache Flink |
| Modos | Batch + Streaming | Batch + Streaming |
| Escala | Auto-scaling (1 a N workers) | Auto-scaling |

## Qué es batch y qué es streaming

| Concepto | Batch (lotes) | Streaming (continuo) |
|---|---|---|
| **Analogía** | Lavadora: acumulas ropa, lavas todo junto | Grifo: el agua fluye constantemente |
| **Cómo procesa** | Acumula datos → procesa todos juntos | Cada dato se procesa al llegar |
| **Latencia** | Minutos a horas | Segundos |
| **Ejemplo** | CSV con 100 orders se sube 1 vez al día | Cada click del usuario se procesa al instante |

## Qué va por batch y qué por streaming en nuestro E-commerce

| Entidad | Camino | Por qué |
|---|---|---|
| customers | **Batch** (CSV → Function → Bronze) | Se registran pocas veces al día, no es urgente |
| products | **Batch** (CSV → Function → Bronze) | Catálogo cambia poco, un CSV diario es suficiente |
| orders | **Batch** (CSV → Function → Bronze) | Se exportan en lotes desde PostgreSQL |
| order_items | **Batch** (CSV → Function → Bronze) | Va junto con orders |
| payments | **Batch** (CSV → Function → Bronze) | Se exportan en lotes |
| inventory | **Batch** (CSV → Function → Bronze) | Actualización periódica |
| reviews | **Batch** (CSV → Function → Bronze) | No es urgente |
| **events (clickstream)** | **Streaming** (Pub/Sub → Dataflow → Bronze) | Alto volumen, tiempo real, no hay CSV |

### Por qué solo ClickEvents en streaming

1. **Volumen alto** — 1 usuario genera 20-50 eventos por sesión. 10,000 usuarios = 500,000 eventos/hora
2. **Tiempo real importa** — quieres ver el funnel de conversión en vivo, no de hace 1 hora
3. **No hay CSV** — los clicks no se exportan a archivo, se envían directamente desde el navegador del usuario
4. **Las demás entidades** — un customer se crea 1 vez, un producto se actualiza 1 vez al mes. No justifica el costo de Dataflow (~$50/mes)

---

## Flujo completo: ambos caminos coexisten

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  BATCH (lo que ya tenemos — 7 entidades):                       │
│                                                                 │
│  customers.csv  ─┐                                              │
│  products.csv   ─┤                                              │
│  orders.csv     ─┤→ GCS → Pub/Sub → Cloud Function → Bronze    │
│  order_items.csv─┤                                              │
│  payments.csv   ─┤   Frecuencia: por upload de CSV              │
│  inventory.csv  ─┤   Latencia: minutos                          │
│  reviews.csv    ─┘                                              │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  STREAMING (nuevo — solo ClickEvents):                          │
│                                                                 │
│  Navegador del usuario                                          │
│  (page_view, product_view, search,                              │
│   add_to_cart, checkout_start, purchase)                        │
│       │                                                         │
│       ▼                                                         │
│  Pub/Sub topic "realtime-events"                                │
│       │                                                         │
│       ▼                                                         │
│  Dataflow (Apache Beam pipeline)                                │
│       │                                                         │
│       ▼                                                         │
│  bronze.events_raw                                              │
│                                                                 │
│  Frecuencia: continuo (cada evento al instante)                 │
│  Latencia: 3-5 segundos                                         │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ORQUESTACIÓN (Composer — ya lo tenemos):                       │
│                                                                 │
│  Bronze → Silver (MERGE cada 3 min)                             │
│  Aplica a TODOS — batch y streaming llegan a Bronze             │
│                                                                 │
│  Gold → vistas (se calculan solas al consultar)                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Impacto en el negocio

### Qué puedes hacer con streaming de ClickEvents que NO puedes con batch

| Caso de uso | Con batch (CSV cada hora) | Con streaming (Dataflow) |
|---|---|---|
| **Funnel en vivo** | Ves datos de hace 1 hora | Ves conversión en tiempo real |
| **Carrito abandonado** | Email al día siguiente | Push notification en 2 minutos |
| **Personalización** | Basada en historial de ayer | Basada en lo que el usuario está viendo ahora |
| **A/B testing** | Resultados mañana | Resultados en minutos |
| **Alertas de caída** | Te enteras cuando un cliente se queja | Alerta si los eventos paran por 5 min |
| **Black Friday** | Dashboard desactualizado | Dashboard en vivo, stock en tiempo real |

### Ejemplo: Black Friday

```
Sin streaming:
  10:00  — Miles de usuarios comprando
  10:30  — El CSV batch se procesa, datos de hace 30 min
  10:40  — Dashboard muestra funnel desactualizado
  10:45  — No sabes que el checkout está fallando desde las 10:05

Con streaming:
  10:00  — Miles de usuarios comprando
  10:00:05 — Cada click se procesa en <5 segundos
  10:05:00 — Dashboard muestra que checkout_start subió pero purchase bajó
  10:05:30 — Alerta: "conversion rate cayó 50% en los últimos 5 minutos"
  10:06:00 — Investigas y encuentras un bug en el checkout
```

---

## Arquitectura del streaming

```
┌──────────────────────┐
│   Navegador usuario  │
│                      │
│  onClick → event:    │
│  {                   │
│    event_id: "rt-x", │
│    event_type:       │
│      "product_view", │
│    customer_id:      │
│      "cust-001",     │
│    product_id:       │
│      "prod-005",     │
│    device: "mobile", │
│    timestamp: "..."  │
│  }                   │
└──────────┬───────────┘
           │ HTTP POST (desde JS SDK o API)
           ▼
┌──────────────────────┐
│      Pub/Sub         │
│                      │
│  Topic:              │
│  realtime-events     │
│                      │
│  Cada mensaje =      │
│  1 evento de click   │
└──────────┬───────────┘
           │ Streaming pull (continuo)
           ▼
┌──────────────────────────────────────┐
│         Dataflow (Apache Beam)        │
│                                      │
│  Pipeline streaming:                 │
│                                      │
│  1. Lee de Pub/Sub (nunca termina)   │
│  2. Parsea JSON del evento           │
│  3. Valida (event_id, event_type)    │
│  4. Descarta eventos inválidos       │
│  5. Escribe en BigQuery Bronze       │
│     (streaming inserts)              │
│                                      │
│  Workers: 1-2 (auto-scaling)         │
│  SA: sa-functions                    │
│  Región: europe-west1               │
└──────────┬───────────────────────────┘
           │
           ▼
┌──────────────────────┐
│  BigQuery Bronze     │
│  events_raw          │
│                      │
│  event_id            │
│  event_type          │
│  raw_payload (JSON)  │
│  source:             │
│   "streaming/pubsub" │
│  ingested_at         │
└──────────────────────┘
           │
           │ Composer MERGE (cada 3 min)
           ▼
┌──────────────────────┐
│  BigQuery Silver     │
│  events              │
│  (particionado,      │
│   clusterizado)      │
└──────────────────────┘
           │
           │ Vista automática
           ▼
┌──────────────────────┐
│  BigQuery Gold       │
│  conversion_funnel   │
│  (tiempo real)       │
└──────────────────────┘
```

---

## Paso a paso

### Paso 1 — Habilitar API de Dataflow

```bash
gcloud services enable dataflow.googleapis.com
```

Verificar:
```bash
gcloud services list --enabled | grep dataflow
```

### Paso 2 — Crear topic de Pub/Sub para streaming

> Este topic es **diferente** al de batch (`csv-uploaded`).
> `csv-uploaded` → recibe notificaciones de Cloud Storage (CSVs)
> `realtime-events` → recibe clicks del usuario directamente

```bash
gcloud pubsub topics create realtime-events
```

Verificar:
```bash
gcloud pubsub topics list
```

Debe mostrar ambos:
```
csv-uploaded        ← batch (CSVs)
csv-uploaded-dlq    ← DLQ del batch
realtime-events     ← streaming (clicks) ← NUEVO
```

### Paso 3 — Crear bucket temporal para Dataflow

> Dataflow necesita un bucket para archivos temporales (staging del código, checkpoints).
> No es para datos — es para que Dataflow funcione internamente.

```bash
gsutil mb -l EU "gs://project-dev-490218-dataflow-temp"
```

### Paso 4 — Dar permisos a sa-functions

> `sa-functions` es la SA (Service Account) que Dataflow usa para ejecutar el pipeline.
> Necesita permisos de Dataflow, Compute (para crear workers) y BigQuery (para escribir).

```bash
gcloud projects add-iam-policy-binding project-dev-490218 --member="serviceAccount:sa-functions@project-dev-490218.iam.gserviceaccount.com" --role="roles/dataflow.worker"

gcloud projects add-iam-policy-binding project-dev-490218 --member="serviceAccount:sa-functions@project-dev-490218.iam.gserviceaccount.com" --role="roles/dataflow.admin"

gcloud projects add-iam-policy-binding project-dev-490218 --member="serviceAccount:sa-functions@project-dev-490218.iam.gserviceaccount.com" --role="roles/compute.viewer"
```

> `sa-functions` ya tiene `bigquery.dataEditor` y `pubsub.subscriber` de configuraciones anteriores.

### Paso 5 — Instalar Apache Beam

```bash
cd /Users/appleuser/Desktop/GPC/pub-sub/dataflow
pip install apache-beam[gcp] google-cloud-pubsub
```

Verificar:
```bash
python -c "import apache_beam; print(apache_beam.__version__)"
```

### Paso 6 — El pipeline (ya creado)

El código está en `pub-sub/dataflow/streaming_pipeline.py`.

Qué hace:

```
1. ReadFromPubSub    → Lee mensajes del topic "realtime-events" (continuo, nunca termina)
2. ParseEvent        → Parsea JSON, valida event_id y event_type, descarta inválidos
3. WriteToBigQuery   → Inserta en bronze.events_raw con streaming inserts
```

| Paso del pipeline | Qué hace | Si falla |
|---|---|---|
| ReadFromPubSub | Lee cada mensaje al llegar | Pub/Sub reintenta |
| ParseEvent | Valida y transforma | Descarta evento inválido, logea warning |
| WriteToBigQuery | Inserta en Bronze | Beam reintenta automáticamente |

### Paso 7 — Lanzar el pipeline en Dataflow

> **Tarda ~5-8 minutos** en arrancar. Dataflow crea VMs (workers) que procesan los datos.

```bash
cd /Users/appleuser/Desktop/GPC/pub-sub/dataflow

python streaming_pipeline.py \
  --project=project-dev-490218 \
  --region=europe-west1 \
  --runner=DataflowRunner \
  --temp_location=gs://project-dev-490218-dataflow-temp/tmp \
  --staging_location=gs://project-dev-490218-dataflow-temp/staging \
  --streaming \
  --service_account_email=sa-functions@project-dev-490218.iam.gserviceaccount.com \
  --max_num_workers=2 \
  --machine_type=n1-standard-1 \
  --job_name=ecommerce-clickevents
```

| Parámetro | Valor | Por qué |
|---|---|---|
| `--runner=DataflowRunner` | Ejecutar en la nube (no local) | Escala, no depende de tu máquina |
| `--streaming` | Modo streaming (pipeline continuo) | Nunca termina, procesa al llegar |
| `--max_num_workers=2` | Máximo 2 VMs | Limitar costos para demo |
| `--machine_type=n1-standard-1` | VM pequeña (1 vCPU, 3.75GB RAM) | Suficiente para tráfico bajo |
| `--job_name` | Nombre del job | Para identificarlo en la consola |

Verificar que arrancó:
```bash
gcloud dataflow jobs list --region=europe-west1 --status=active
```

### Paso 8 — Ver el pipeline en la consola GCP

1. Console → **Dataflow** → **Jobs**
2. Click en `ecommerce-clickevents`
3. Verás el grafo del pipeline:

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ Read from    │ ──▶ │ Parse Event  │ ──▶ │ Write to     │
│ Pub/Sub      │     │              │     │ Bronze       │
│              │     │              │     │              │
│ Elements: 0  │     │ Elements: 0  │     │ Rows: 0      │
│ (esperando)  │     │              │     │              │
└──────────────┘     └──────────────┘     └──────────────┘
```

4. Pestaña **Metrics** → throughput, latencia, errores
5. Pestaña **Logs** → ver mensajes en Cloud Logging
6. Pestaña **Autoscaling** → cuántos workers están activos

### Paso 9 — Publicar eventos de prueba (manual)

Simular clicks del usuario:

```bash
# page_view
gcloud pubsub topics publish realtime-events --message='{"event_id":"rt-001","event_type":"page_view","customer_id":"cust-001","session_id":"sess-100","product_id":null,"search_query":null,"page_url":"/home","device":"mobile","timestamp":"2026-03-16T12:00:01Z"}'

# product_view
gcloud pubsub topics publish realtime-events --message='{"event_id":"rt-002","event_type":"product_view","customer_id":"cust-001","session_id":"sess-100","product_id":"prod-001","search_query":null,"page_url":"/products/prod-001","device":"mobile","timestamp":"2026-03-16T12:00:05Z"}'

# add_to_cart
gcloud pubsub topics publish realtime-events --message='{"event_id":"rt-003","event_type":"add_to_cart","customer_id":"cust-001","session_id":"sess-100","product_id":"prod-001","search_query":null,"page_url":"/cart","device":"mobile","timestamp":"2026-03-16T12:00:10Z"}'

# purchase
gcloud pubsub topics publish realtime-events --message='{"event_id":"rt-004","event_type":"purchase","customer_id":"cust-001","session_id":"sess-100","product_id":null,"search_query":null,"page_url":"/order-confirmation","device":"mobile","timestamp":"2026-03-16T12:00:15Z"}'
```

### Paso 10 — Verificar en BigQuery

Espera ~10-15 segundos después de publicar:

```bash
bq query --use_legacy_sql=false '
SELECT event_id, event_type, source, ingested_at
FROM bronze.events_raw
WHERE source = "streaming/pubsub"
ORDER BY ingested_at DESC
LIMIT 10
'
```

Debe mostrar los 4 eventos con `source = "streaming/pubsub"`.

> **Comparar con batch:** Los eventos de batch tienen `source = "gcs/events/events.csv"`.
> Así sabes cuáles llegaron por streaming y cuáles por CSV.

### Paso 11 — Simular tráfico con la app de consola

Hay una app interactiva que simula **sesiones completas de usuarios** navegando la tienda.
Cada usuario sigue un flujo realista:

```
👤 Entra a la tienda → navega páginas → busca "laptop" → ve productos →
   agrega al carrito → a veces quita algo → inicia checkout → compra o abandona
```

Cada acción se publica como un evento en Pub/Sub → Dataflow lo procesa → llega a Bronze.

**Instalar dependencia:**
```bash
pip install google-cloud-pubsub
```

**Ejecutar (5 usuarios, velocidad normal):**
```bash
cd /Users/appleuser/Desktop/GPC/pub-sub/dataflow
python click_simulator.py
```

**Opciones:**
```bash
# 1 usuario lento (ver evento por evento)
python click_simulator.py --users 1 --speed slow

# 10 usuarios rápido
python click_simulator.py --users 10 --speed fast

# Loop infinito (simula tienda abierta 24/7)
python click_simulator.py --users 5 --speed normal --loop
```

**Output en consola:**
```
╔══════════════════════════════════════════════════════════╗
║         Simulador de ClickEvents — E-commerce           ║
║  Usuarios: 5       Velocidad: normal    Loop: No        ║
║  Cada evento se publica en Pub/Sub → Dataflow → Bronze  ║
╚══════════════════════════════════════════════════════════╝

  ============================================================
  👤 Maria Garcia (cust-0001) entró a la tienda [mobile]
  ============================================================
  [page_view            ] cust-0001
  [page_view            ] cust-0001
  [search               ] cust-0001 → "laptop"
  [product_view         ] cust-0001 → Laptop Pro 15 ($1299.99)
  [product_view         ] cust-0001 → Mouse Wireless ($29.99)
  [add_to_cart          ] cust-0001 → Laptop Pro 15
  [add_to_cart          ] cust-0001 → Mouse Wireless
  [checkout_start       ] cust-0001
  [purchase             ] cust-0001 🎉
  ────────────────────────────────────────────────────────────
  💰 Maria Garcia compró 2 producto(s) por $1329.98

  ============================================================
  👤 Juan Lopez (cust-0002) entró a la tienda [desktop]
  ============================================================
  [page_view            ] cust-0002
  [product_view         ] cust-0002 → Silla Ergonomica ($349.99)
  [add_to_cart          ] cust-0002 → Silla Ergonomica
  [remove_from_cart     ] cust-0002
  ────────────────────────────────────────────────────────────
  ❌ Juan Lopez vació su carrito y se fue

  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  📊 Estadísticas (Ronda 1)
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Total eventos:     47
  page_view:         15
  search:            4
  product_view:      12
  add_to_cart:       8
  remove_from_cart:  2
  checkout_start:    3
  purchase:          3

  View → Cart rate:  66.7%
  Checkout → Buy:    100.0%
```

**También existe `simulate_traffic.py`** para tráfico simple sin sesiones (1-3 eventos/seg aleatorios):

```bash
python simulate_traffic.py
```

**Mientras corre**, ve a la consola de Dataflow → verás los contadores subiendo en tiempo real.

**Verificar en BigQuery:**
```bash
bq query --use_legacy_sql=false '
SELECT event_type, COUNT(*) as total
FROM bronze.events_raw
WHERE source = "streaming/pubsub"
GROUP BY event_type
ORDER BY total DESC
'
```

### Paso 12 — APAGAR el pipeline (ahorrar créditos)

> **Dataflow cobra por las VMs workers.** Un pipeline streaming nunca termina — hay que pararlo manualmente.

```bash
# Ver el JOB_ID
gcloud dataflow jobs list --region=europe-west1 --status=active
```

```bash
# Drain (recomendado) — termina de procesar lo pendiente y para
gcloud dataflow jobs drain JOB_ID --region=europe-west1
```

```bash
# O cancel (inmediato) — para sin procesar lo pendiente
gcloud dataflow jobs cancel JOB_ID --region=europe-west1
```

**Desde consola:** Dataflow → Jobs → click en el job → **Stop** → **Drain**

Verificar que paró:
```bash
gcloud dataflow jobs list --region=europe-west1 --status=active
```

Debe mostrar 0 jobs activos.

---

## Cómo se distinguen batch y streaming en Bronze

Ambos caminos escriben en la **misma tabla** `bronze.events_raw`, pero con `source` diferente:

```sql
SELECT source, COUNT(*) as eventos
FROM bronze.events_raw
GROUP BY source
```

| source | Camino | Cómo llegó |
|---|---|---|
| `gcs/events/events.csv` | Batch | CSV subido a Cloud Storage |
| `streaming/pubsub` | Streaming | Pub/Sub → Dataflow |

---

## Costos

| Componente | Costo aprox |
|---|---|
| Dataflow (1 worker n1-standard-1) | ~$0.07/hora |
| Pub/Sub (streaming messages) | ~$0.06/GB |
| BigQuery (streaming inserts) | $0.01/200MB |
| **Demo de 1 hora** | **~$0.10** |
| **Corriendo 24/7 (1 worker)** | **~$50/mes** |

> **Para demo:** Lanzar, probar 30 min, apagar. Costo: ~$0.05

---

## Archivos

```
pub-sub/dataflow/
├── README.md                  ← este archivo
├── streaming_pipeline.py      ← pipeline Beam: Pub/Sub → BigQuery Bronze
├── Dockerfile                 ← empaqueta el pipeline en un container Docker
├── metadata.json              ← parámetros del Flex Template
├── click_simulator.py         ← app de consola: simula sesiones de usuario completas
├── simulate_traffic.py        ← simulador simple: eventos aleatorios 1-3/seg
└── requirements.txt           ← dependencias (apache-beam[gcp])

.github/workflows/
├── terraform.yml              ← CI/CD de infraestructura (ya existía)
└── deploy-pipeline.yml        ← CI/CD del pipeline Dataflow (NUEVO)
```

| Archivo | Para qué | Cuándo usar |
|---|---|---|
| `streaming_pipeline.py` | El pipeline de Dataflow que corre en GCP | Siempre — es el procesador |
| `Dockerfile` | Empaqueta el pipeline en Docker (Flex Template) | Producción — CI/CD lo construye |
| `metadata.json` | Define parámetros del template | Producción — Dataflow lo lee |
| `deploy-pipeline.yml` | CI/CD: build → push → deploy automático | Producción — se activa al hacer push |
| `click_simulator.py` | Simula usuarios con sesiones realistas | Demo, presentaciones, testing |
| `simulate_traffic.py` | Genera eventos aleatorios rápido | Load testing, llenar Bronze rápido |

---

## Deploy en producción (CI/CD)

### Cómo funciona

```
Developer cambia streaming_pipeline.py
        │
        ▼
Push a GitHub (branch → PR → merge a main)
        │
        ▼
GitHub Actions (deploy-pipeline.yml):
        │
        ├── 1. Build: docker build → crea imagen con el pipeline
        │
        ├── 2. Push: docker push → sube imagen a Artifact Registry
        │         (europe-west1-docker.pkg.dev/project-dev-490218/
        │          dataflow-pipelines/streaming-pipeline:SHA)
        │
        ├── 3. Template: gcloud dataflow flex-template build
        │         → crea template en GCS apuntando a la imagen
        │
        ├── 4. Drain: para el job anterior (termina lo pendiente)
        │
        └── 5. Run: gcloud dataflow flex-template run
                  → lanza nuevo pipeline con la imagen nueva
```

### Qué es cada pieza

| Pieza | Qué es | Para qué |
|---|---|---|
| **Dockerfile** | Receta para construir la imagen Docker | Empaqueta tu código + dependencias en un container |
| **Artifact Registry** | Almacén de imágenes Docker en GCP | Guarda las versiones de tu pipeline |
| **Flex Template** | JSON en GCS que apunta a la imagen | Le dice a Dataflow "usa esta imagen para correr el pipeline" |
| **deploy-pipeline.yml** | Workflow de GitHub Actions | Automatiza todo: build → push → drain → deploy |

### Versionado y rollback

```
Commit abc123 → imagen :abc123 → pipeline v1 corriendo
Commit def456 → imagen :def456 → pipeline v2 corriendo (v1 se drainea)
        │
        │ Algo falla en v2?
        ▼
Relanzar manualmente con imagen :abc123
gcloud dataflow flex-template run ecommerce-clickevents \
  --template-file-gcs-location=gs://project-dev-490218-dataflow-temp/templates/streaming-pipeline.json \
  --region=europe-west1 \
  ...
```

Cada commit genera una imagen con su SHA como tag. Puedes volver a cualquier versión.

### Permisos adicionales para CI/CD

`sa-pipeline` necesita estos roles para que el workflow funcione:

```bash
# Artifact Registry — push de imágenes Docker
gcloud projects add-iam-policy-binding project-dev-490218 \
  --member="serviceAccount:sa-pipeline@project-dev-490218.iam.gserviceaccount.com" \
  --role="roles/artifactregistry.writer"

# Dataflow — lanzar y drain jobs
gcloud projects add-iam-policy-binding project-dev-490218 \
  --member="serviceAccount:sa-pipeline@project-dev-490218.iam.gserviceaccount.com" \
  --role="roles/dataflow.admin"
```

### Demo (CLI) vs Producción (CI/CD)

| Aspecto | Demo (CLI) | Producción (CI/CD) |
|---|---|---|
| Cómo se lanza | `python streaming_pipeline.py` desde tu terminal | Push a GitHub → se despliega solo |
| Dónde está el código | En tu máquina | En Artifact Registry (Docker image) |
| Versiones | No hay | Cada commit = una versión |
| Rollback | No hay — relanzas manual | Relanzar con imagen anterior |
| Actualizar | Matas el job y relanzas manual | Push a main → drain viejo → lanza nuevo |
| Depende de tu máquina | Sí (para lanzar) | No — todo en la nube |

---

## Checklist

### Demo (CLI)
- [ ] API de Dataflow habilitada
- [ ] Topic `realtime-events` creado
- [ ] Bucket temporal `project-dev-490218-dataflow-temp` creado
- [ ] Permisos de sa-functions configurados
- [ ] Apache Beam instalado
- [ ] Pipeline lanzado con `python streaming_pipeline.py`
- [ ] Eventos verificados en Bronze
- [ ] **Pipeline apagado después de probar**

### Producción (CI/CD)
- [ ] Dockerfile creado
- [ ] metadata.json creado
- [ ] deploy-pipeline.yml creado
- [ ] Permisos de sa-pipeline: `artifactregistry.writer`, `dataflow.admin`
- [ ] Push a main → workflow corre automáticamente
- [ ] Imagen en Artifact Registry
- [ ] Pipeline corriendo en Dataflow
- [ ] Verificar rollback funciona
