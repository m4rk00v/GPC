# Apache Beam — Conceptos y cómo implementarlos en el proyecto

## Estado actual vs lo que falta

| Concepto | Implementado | Prioridad | Impacto |
|---|---|---|---|
| PCollection | Sí | — | — |
| DoFn | Sí | — | — |
| Exactly-once | Sí (Dataflow lo hace) | — | — |
| Auto-scaling | Sí (`max_num_workers`) | — | — |
| **DirectRunner** | No | Alta | Evita ciclos de debug de 10 min |
| **TaggedOutput** | No | Alta | No perder eventos inválidos |
| **Windowing** | No | Media | Métricas en tiempo real (funnel, alertas) |
| **Flatten** | No | Baja | Solo si hay múltiples topics |
| **Batch mode** | No en Dataflow | Baja | El batch ya lo hace Cloud Function |

---

## 1. DirectRunner — Test local antes de deploy

### Qué es

Ejecutar el pipeline en tu máquina en vez de en Dataflow. Detectas errores en 5 segundos, no en 10 minutos.

### Sin DirectRunner (hoy)

```
Cambias código → push → CI/CD → Dataflow tarda 8 min → falla por un typo → repites
Total: 20 minutos perdidos por un error de sintaxis
```

### Con DirectRunner

```
Cambias código → python streaming_pipeline.py --runner=DirectRunner → falla en 5 seg → arreglas → push
Total: 30 segundos
```

### Cómo implementarlo

**1. Script de test local (`test_pipeline.py`):**

```python
"""
Test del pipeline con DirectRunner.
Simula mensajes de Pub/Sub y verifica que se parsean correctamente.
No necesita GCP — corre 100% en tu máquina.

Ejecutar: python test_pipeline.py
"""

import json
import apache_beam as beam
from apache_beam.testing.test_pipeline import TestPipeline
from apache_beam.testing.util import assert_that, equal_to
from streaming_pipeline import ParseEvent


def test_parse_valid_event():
    """Evento válido se parsea correctamente."""
    input_data = [
        json.dumps({
            "event_id": "rt-001",
            "event_type": "page_view",
            "customer_id": "cust-001",
            "session_id": "sess-100",
            "product_id": None,
            "page_url": "/home",
            "device": "mobile",
            "timestamp": "2026-03-16T12:00:00Z"
        }).encode("utf-8")
    ]

    with TestPipeline() as p:
        output = (
            p
            | beam.Create(input_data)
            | beam.ParDo(ParseEvent())
        )

        assert_that(output, equal_to([{
            "event_id": "rt-001",
            "event_type": "page_view",
            "raw_payload": json.dumps({
                "event_id": "rt-001",
                "event_type": "page_view",
                "customer_id": "cust-001",
                "session_id": "sess-100",
                "product_id": None,
                "page_url": "/home",
                "device": "mobile",
                "timestamp": "2026-03-16T12:00:00Z"
            }),
            "source": "streaming/pubsub",
            "ingested_at": output[0]["ingested_at"],  # timestamp dinámico
        }]))


def test_parse_invalid_event():
    """Evento sin event_id se descarta (no produce output)."""
    input_data = [
        json.dumps({"some_field": "some_value"}).encode("utf-8")
    ]

    with TestPipeline() as p:
        output = (
            p
            | beam.Create(input_data)
            | beam.ParDo(ParseEvent())
        )

        assert_that(output, equal_to([]))


def test_parse_bad_json():
    """JSON inválido se descarta."""
    input_data = [b"this is not json"]

    with TestPipeline() as p:
        output = (
            p
            | beam.Create(input_data)
            | beam.ParDo(ParseEvent())
        )

        assert_that(output, equal_to([]))


if __name__ == "__main__":
    test_parse_valid_event()
    print("✓ test_parse_valid_event passed")

    test_parse_invalid_event()
    print("✓ test_parse_invalid_event passed")

    test_parse_bad_json()
    print("✓ test_parse_bad_json passed")

    print("\nAll tests passed!")
```

**2. Agregar al CI/CD (antes del deploy):**

```yaml
# En deploy-pipeline.yml, antes del job "deploy":
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install "apache-beam[gcp]"
      - run: python pub-sub/dataflow/test_pipeline.py
```

### Ventaja

| Sin DirectRunner | Con DirectRunner |
|---|---|
| Errores se detectan en Dataflow (8 min) | Errores se detectan en CI (30 seg) |
| Deploy fallido gasta $$ en VMs | Test local es gratis |
| No sabes si el parseo funciona hasta producción | Tests verifican cada caso |

---

## 2. TaggedOutput — No perder eventos inválidos

### Qué es

Enviar cada elemento a diferentes salidas según una condición. Los eventos válidos van a BigQuery, los inválidos van a una tabla de errores para análisis.

### Sin TaggedOutput (hoy)

```python
# Evento inválido → se descarta silenciosamente
if not event_id or not event_type:
    logging.warning(f"Evento sin event_id")
    return  # ← se pierde para siempre
```

### Con TaggedOutput

```python
# Evento inválido → va a una tabla de errores
if not event_id or not event_type:
    yield beam.pvalue.TaggedOutput('invalid', {
        "raw_message": raw,
        "error": "missing event_id or event_type",
        "timestamp": datetime.utcnow().isoformat(),
    })
    return

yield beam.pvalue.TaggedOutput('valid', {
    "event_id": event_id,
    ...
})
```

### Cómo implementarlo

**Modificar `streaming_pipeline.py`:**

```python
from apache_beam import DoFn, ParDo, pvalue

class ParseEvent(beam.DoFn):
    # Definir las salidas posibles
    VALID = 'valid'
    INVALID = 'invalid'

    def process(self, element):
        try:
            raw = element.decode("utf-8") if isinstance(element, bytes) else element
            event = json.loads(raw)

            event_id = event.get("event_id")
            event_type = event.get("event_type")

            if not event_id or not event_type:
                # Evento inválido → sale por 'invalid'
                yield pvalue.TaggedOutput(self.INVALID, {
                    "raw_message": raw[:10000],
                    "error_type": "missing_required_fields",
                    "error_detail": f"event_id={event_id}, event_type={event_type}",
                    "source": "streaming/pubsub",
                    "error_timestamp": datetime.utcnow().isoformat(),
                })
                return

            # Evento válido → sale por 'valid'
            yield pvalue.TaggedOutput(self.VALID, {
                "event_id": event_id,
                "event_type": event_type,
                "raw_payload": json.dumps(event, ensure_ascii=False),
                "source": "streaming/pubsub",
                "ingested_at": datetime.utcnow().isoformat(),
            })

        except json.JSONDecodeError as e:
            yield pvalue.TaggedOutput(self.INVALID, {
                "raw_message": str(element)[:10000],
                "error_type": "invalid_json",
                "error_detail": str(e),
                "source": "streaming/pubsub",
                "error_timestamp": datetime.utcnow().isoformat(),
            })


# En el pipeline:
parsed = (
    p
    | "Read" >> beam.io.ReadFromPubSub(topic=TOPIC)
    | "Parse" >> beam.ParDo(ParseEvent()).with_outputs(
        ParseEvent.VALID,
        ParseEvent.INVALID
    )
)

# Eventos válidos → BigQuery Bronze
parsed[ParseEvent.VALID] | "Write Valid" >> WriteToBigQuery(
    table=BRONZE_TABLE,
    ...
)

# Eventos inválidos → BigQuery tabla de errores
parsed[ParseEvent.INVALID] | "Write Invalid" >> WriteToBigQuery(
    table=f"{PROJECT_ID}:bronze.events_errors",
    schema=ERROR_SCHEMA,
    ...
)
```

**Crear tabla de errores en Terraform (`bigquery/bronze/main.tf`):**

```hcl
resource "google_bigquery_table" "events_errors" {
  dataset_id            = google_bigquery_dataset.bronze.dataset_id
  table_id              = "events_errors"
  project               = var.project_id
  deletion_protection   = false

  schema = jsonencode([
    { name = "raw_message", type = "STRING", mode = "NULLABLE" },
    { name = "error_type", type = "STRING", mode = "NULLABLE" },
    { name = "error_detail", type = "STRING", mode = "NULLABLE" },
    { name = "source", type = "STRING", mode = "NULLABLE" },
    { name = "error_timestamp", type = "TIMESTAMP", mode = "NULLABLE" }
  ])
}
```

### Ventaja

| Sin TaggedOutput | Con TaggedOutput |
|---|---|
| Eventos inválidos desaparecen | Se guardan en `bronze.events_errors` |
| No sabes cuántos eventos se pierden | Query: `SELECT COUNT(*) FROM bronze.events_errors` |
| No puedes debuggear por qué falló | Tienes `error_type` y `error_detail` |
| No puedes reprocesar | Tienes `raw_message` para reprocesar |

---

## 3. Windowing — Métricas en ventanas de tiempo

### Qué es

Agrupar eventos por ventanas de tiempo. En vez de procesar evento por evento, calculas métricas sobre "los últimos 5 minutos".

### Sin Windowing (hoy)

```
Cada evento → se guarda en Bronze individual → fin
Para ver "clicks últimos 5 min" → query SQL después (no en tiempo real)
```

### Con Windowing

```
Eventos de los últimos 5 min → Dataflow los agrupa → calcula métricas → escribe resultado
"En los últimos 5 min: 150 page_views, 45 product_views, 12 add_to_cart, 3 purchases"
Eso se actualiza cada 5 minutos automáticamente
```

### Tipos de ventana

```
FIXED (Tumbling) — ventanas fijas sin solapamiento:
|── 10:00-10:05 ──|── 10:05-10:10 ──|── 10:10-10:15 ──|

SLIDING — ventanas que se solapan:
|── 10:00-10:05 ──|
   |── 10:01-10:06 ──|
      |── 10:02-10:07 ──|

SESSION — ventana por actividad del usuario:
|── usuario activo ──|  (30 min sin actividad)  |── usuario vuelve ──|
```

### Cómo implementarlo

**Agregar windowing al pipeline:**

```python
from apache_beam import window
from apache_beam.transforms.combiners import CountCombineFn

# Después de parsear, agregar windowing:
windowed_counts = (
    parsed[ParseEvent.VALID]
    # Ventana fija de 5 minutos
    | "Window 5min" >> beam.WindowInto(window.FixedWindows(5 * 60))

    # Contar eventos por tipo en cada ventana
    | "Extract type" >> beam.Map(lambda e: (e["event_type"], 1))
    | "Count by type" >> beam.CombinePerKey(sum)

    # Formatear para BigQuery
    | "Format" >> beam.Map(lambda kv: {
        "window_start": None,  # Beam agrega automáticamente
        "event_type": kv[0],
        "event_count": kv[1],
        "calculated_at": datetime.utcnow().isoformat(),
    })
)

# Escribir métricas de ventana en Silver
windowed_counts | "Write Metrics" >> WriteToBigQuery(
    table=f"{PROJECT_ID}:silver.event_metrics_5min",
    schema=METRICS_SCHEMA,
    ...
)
```

**Crear tabla de métricas en Terraform (`bigquery/silver/main.tf`):**

```hcl
resource "google_bigquery_table" "event_metrics_5min" {
  dataset_id = google_bigquery_dataset.silver.dataset_id
  table_id   = "event_metrics_5min"
  project    = var.project_id

  time_partitioning {
    type  = "DAY"
    field = "window_start"
  }

  schema = jsonencode([
    { name = "window_start", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "window_end", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "event_type", type = "STRING", mode = "NULLABLE" },
    { name = "event_count", type = "INT64", mode = "NULLABLE" },
    { name = "calculated_at", type = "TIMESTAMP", mode = "NULLABLE" }
  ])
}
```

**Resultado en Silver cada 5 minutos:**

```
window_start         | event_type    | event_count
2026-03-16 10:00:00  | page_view     | 150
2026-03-16 10:00:00  | product_view  | 45
2026-03-16 10:00:00  | add_to_cart   | 12
2026-03-16 10:00:00  | purchase      | 3
2026-03-16 10:05:00  | page_view     | 180
2026-03-16 10:05:00  | product_view  | 52
...
```

### Ventaja

| Sin Windowing | Con Windowing |
|---|---|
| Para ver "clicks últimos 5 min" → query SQL | Ya calculado, listo para dashboard |
| Query escanea toda la tabla | Tabla pequeña con métricas pre-calculadas |
| Latencia: depende de cuándo corres el query | Latencia: 5 minutos (tamaño de ventana) |
| No puedes detectar caídas en tiempo real | Alerta si `event_count = 0` en una ventana |
| Dashboard lento (query pesado) | Dashboard rápido (lee tabla chica) |

### Caso de uso: Alerta de caída

```sql
-- Si no hubo purchase en los últimos 15 minutos → algo anda mal
SELECT window_start, event_count
FROM silver.event_metrics_5min
WHERE event_type = 'purchase'
  AND window_start > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 15 MINUTE)
  AND event_count = 0
```

---

## 4. Flatten — Unir múltiples fuentes

### Qué es

Combinar PCollections de diferentes orígenes en una sola. Como un `UNION ALL`.

### Cuándo lo necesitaríamos

Si la tienda tiene **múltiples fuentes de eventos**:

```
Topic: realtime-events-web      (clicks del navegador)
Topic: realtime-events-mobile   (clicks de la app)
Topic: realtime-events-pos      (punto de venta físico)
         │           │              │
         └─────── Flatten ──────────┘
                    │
              PCollection unificada
                    │
              Parse → BigQuery Bronze
```

### Cómo implementarlo

```python
# Leer de múltiples topics
web_events = p | "Read Web" >> beam.io.ReadFromPubSub(
    topic=f"projects/{PROJECT_ID}/topics/realtime-events-web"
)
mobile_events = p | "Read Mobile" >> beam.io.ReadFromPubSub(
    topic=f"projects/{PROJECT_ID}/topics/realtime-events-mobile"
)
pos_events = p | "Read POS" >> beam.io.ReadFromPubSub(
    topic=f"projects/{PROJECT_ID}/topics/realtime-events-pos"
)

# Unir en una sola PCollection
all_events = (
    (web_events, mobile_events, pos_events)
    | "Flatten" >> beam.Flatten()
)

# Procesar todos igual
all_events | "Parse" >> beam.ParDo(ParseEvent()) | "Write" >> WriteToBigQuery(...)
```

### Ventaja

| Sin Flatten | Con Flatten |
|---|---|
| Un pipeline por topic (3 pipelines) | Un solo pipeline para todos |
| 3x costo de workers | 1x costo |
| 3 jobs que monitorear | 1 job |
| Lógica duplicada | Lógica centralizada |

### Prioridad: Baja

Solo necesario si hay múltiples canales. Hoy tenemos un solo topic.

---

## 5. Batch mode en Dataflow

### Qué es

Ejecutar un pipeline de Beam que procesa datos finitos (tiene inicio y fin). Lee un archivo, lo procesa, termina.

### Cuándo lo usaríamos

Para **reprocesar** datos históricos de Bronze → Silver:

```python
# Batch: lee un rango de fechas de Bronze y reprocesa a Silver
(
    p
    | "Read Bronze" >> beam.io.ReadFromBigQuery(
        query=f"""
            SELECT * FROM `{PROJECT_ID}.bronze.events_raw`
            WHERE DATE(ingested_at) BETWEEN '2026-01-01' AND '2026-03-01'
        """,
        use_standard_sql=True,
    )
    | "Parse" >> beam.ParDo(ParseEvent())
    | "Write Silver" >> WriteToBigQuery(table=SILVER_TABLE, ...)
)
```

Diferencia con streaming:

| Batch | Streaming |
|---|---|
| `--streaming` no se pone | `--streaming` obligatorio |
| Lee datos, procesa, **termina** | Lee datos, procesa, **nunca termina** |
| Para reprocesar históricos | Para datos en tiempo real |
| Paga por el tiempo que corre | Paga 24/7 |

### Prioridad: Baja

El reproceso hoy lo hace Composer con MERGE SQL. Dataflow batch sería para volúmenes masivos (millones de filas).

---

## Orden de implementación recomendado

| Prioridad | Qué | Por qué | Esfuerzo |
|---|---|---|---|
| 1 | **DirectRunner + tests** | Evita desperdiciar 10 min por typo | 1 hora |
| 2 | **TaggedOutput** | No perder eventos, debuggear errores | 2 horas |
| 3 | **Windowing** | Dashboard en tiempo real, alertas de caída | 3 horas |
| 4 | Flatten | Solo si hay múltiples topics | 1 hora |
| 5 | Batch mode | Solo si necesitas reprocesar masivamente | 2 horas |

---

## Pipeline completo con todo implementado

```python
# Lo que tendríamos con todo:

p = beam.Pipeline(options=options)

# 1. Leer de Pub/Sub (streaming)
raw = p | "Read" >> beam.io.ReadFromPubSub(topic=TOPIC)

# 2. Parsear con TaggedOutput (válidos + inválidos)
parsed = raw | "Parse" >> beam.ParDo(ParseEvent()).with_outputs('valid', 'invalid')

# 3. Eventos válidos → BigQuery Bronze
parsed['valid'] | "Write Bronze" >> WriteToBigQuery(table=BRONZE_TABLE)

# 4. Eventos inválidos → tabla de errores
parsed['invalid'] | "Write Errors" >> WriteToBigQuery(table=ERROR_TABLE)

# 5. Windowing → métricas cada 5 min
(
    parsed['valid']
    | "Window" >> beam.WindowInto(FixedWindows(5 * 60))
    | "Count" >> beam.Map(lambda e: (e["event_type"], 1))
    | "Sum" >> beam.CombinePerKey(sum)
    | "Format" >> beam.Map(format_metric)
    | "Write Metrics" >> WriteToBigQuery(table=METRICS_TABLE)
)

p.run()
```

```
Grafo visual en Dataflow:

                              ┌──────────────┐
                              │  Write       │
                         ┌───▶│  Bronze      │
                         │    └──────────────┘
┌──────────┐   ┌────────┴─┐
│ Read     │──▶│ Parse    │
│ Pub/Sub  │   │ (DoFn)   │  ┌──────────────┐
└──────────┘   └────────┬─┘  │  Write       │
                   │    └───▶│  Errors      │
                   │         └──────────────┘
                   │
                   │    ┌──────────┐  ┌──────────┐  ┌──────────────┐
                   └───▶│ Window   │─▶│ Count    │─▶│  Write       │
                        │ 5 min    │  │ by type  │  │  Metrics     │
                        └──────────┘  └──────────┘  └──────────────┘
```
