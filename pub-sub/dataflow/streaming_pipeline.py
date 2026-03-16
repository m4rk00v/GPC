"""
Dataflow Streaming Pipeline: Pub/Sub → BigQuery Bronze

Lee eventos en tiempo real de Pub/Sub,
los valida, parsea y escribe en BigQuery Bronze.

============================================
CONCEPTOS IMPLEMENTADOS EN ESTE ARCHIVO:
============================================

1. PCollection (Parallel Collection)
   - Qué es: Un conjunto de datos distribuido que fluye por el pipeline.
     Piensa en él como una lista de elementos, pero repartida entre múltiples máquinas.
   - AWS análogo: No tiene equivalente directo. Lo más cercano es un Kinesis Data Stream
     donde los datos fluyen entre pasos, pero PCollection es un concepto de Beam,
     no de infraestructura.
   - Dónde está: Cada paso (|) del pipeline produce una PCollection nueva.
     Línea ~155: PCollection de bytes (mensajes de Pub/Sub)
     Línea ~162: PCollection de dicts (mensajes parseados)

2. DoFn (Do Function)
   - Qué es: Una función que se ejecuta por CADA elemento de una PCollection.
     Es como un map() de Python, pero distribuido entre múltiples máquinas.
     Si tienes 1000 mensajes y 2 workers, cada worker ejecuta el DoFn ~500 veces.
   - AWS análogo: Una función Lambda que procesa cada record de un Kinesis Stream.
     La diferencia es que Lambda crea una instancia por cada invocación,
     mientras que DoFn reutiliza la instancia entre elementos (más eficiente).
   - Dónde está: Clase ParseEvent (línea ~88)

3. Exactly-once (Exactamente una vez)
   - Qué es: Garantía de que cada mensaje se procesa exactamente 1 vez.
     No se pierde (at-least-once) ni se duplica (at-most-once).
     Si un worker muere procesando un mensaje, Dataflow lo reintenta
     en otro worker SIN que el mensaje se escriba 2 veces en BigQuery.
   - AWS análogo: Kinesis + Lambda tiene "at-least-once" (puede duplicar).
     Para exactly-once en AWS necesitas implementar idempotencia manualmente.
     Dataflow lo hace automáticamente con checkpointing interno.
   - Dónde está: Es transparente — Dataflow lo maneja internamente.
     Se activa al usar STREAMING_INSERTS (línea ~177).
     No hay código que escribir — es una propiedad del runner.

4. Auto-scaling (Escalado automático)
   - Qué es: Dataflow ajusta el número de VMs (workers) según la carga.
     Si llegan 10 msgs/seg → 1 worker. Si llegan 10,000/seg → sube a N workers.
     Cuando la carga baja, reduce workers automáticamente.
   - AWS análogo: Kinesis Data Analytics con auto-scaling de KPUs.
     O Lambda que escala automáticamente por invocación.
     La diferencia es que Dataflow escala workers (VMs persistentes),
     no funciones efímeras. Más eficiente para streaming continuo.
   - Dónde está: No es código — es configuración del runner al lanzar:
     --max_num_workers=2 (máximo 2 VMs)
     --machine_type=n1-standard-1 (tipo de VM)

============================================
CONCEPTOS NO IMPLEMENTADOS (ver missing.md):
============================================

5. DirectRunner (Test local)
   - Qué es: Ejecutar el pipeline en tu máquina en vez de en Dataflow.
     Mismo código, diferente runner. Para testing y debug.
   - AWS análogo: Ejecutar un Glue job con pytest localmente.

6. TaggedOutput (Múltiples salidas)
   - Qué es: Enviar cada elemento a diferentes destinos según condición.
     Eventos válidos → BigQuery. Eventos inválidos → tabla de errores.
   - AWS análogo: Kinesis Firehose con transformación Lambda que envía
     a S3 (válidos) y a otra ruta S3 (errores).

7. Windowing (Ventanas de tiempo)
   - Qué es: Agrupar eventos por ventanas de tiempo.
     "Dame los clicks de los últimos 5 minutos."
   - AWS análogo: Kinesis Data Analytics con TUMBLE window en SQL.

8. Flatten (Unir fuentes)
   - Qué es: Combinar múltiples PCollections en una. Como UNION ALL en SQL.
   - AWS análogo: Kinesis con múltiples shards leyendo de múltiples streams.

============================================

Ejecutar en Dataflow (producción):
  python streaming_pipeline.py \\
    --project=project-dev-490218 \\
    --region=us-central1 \\
    --runner=DataflowRunner \\
    --temp_location=gs://project-dev-490218-dataflow-temp/tmp \\
    --staging_location=gs://project-dev-490218-dataflow-temp/staging \\
    --streaming \\
    --service_account_email=sa-functions@project-dev-490218.iam.gserviceaccount.com \\
    --max_num_workers=2 \\
    --machine_type=n1-standard-1

Ejecutar local (testing con DirectRunner):
  python streaming_pipeline.py --runner=DirectRunner --streaming
"""

import json
import logging
from datetime import datetime, timezone

import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions, StandardOptions
from apache_beam.io.gcp.bigquery import WriteToBigQuery, BigQueryDisposition


# ============================================
# Configuración
# ============================================

PROJECT_ID = "project-dev-490218"

# Topic de Pub/Sub de donde lee el pipeline.
# Es como un ARN de SNS/SQS en AWS — identifica el recurso.
TOPIC = f"projects/{PROJECT_ID}/topics/realtime-events"

# Tabla destino en BigQuery (formato: project:dataset.table)
# Es como un ARN de DynamoDB o Redshift en AWS.
BRONZE_TABLE = f"{PROJECT_ID}:bronze.events_raw"

# Schema de la tabla — define las columnas y tipos.
# En AWS sería el schema de un Glue Table o un CREATE TABLE en Redshift.
BRONZE_SCHEMA = {
    "fields": [
        {"name": "event_id", "type": "STRING", "mode": "REQUIRED"},
        {"name": "event_type", "type": "STRING", "mode": "NULLABLE"},
        {"name": "raw_payload", "type": "STRING", "mode": "NULLABLE"},
        {"name": "source", "type": "STRING", "mode": "NULLABLE"},
        {"name": "ingested_at", "type": "TIMESTAMP", "mode": "NULLABLE"},
    ]
}


# ============================================
# DoFn (Do Function) — CONCEPTO #2
#
# ¿Qué es?
#   Una clase que define qué hacer con CADA elemento de datos.
#   Beam toma tu DoFn y lo ejecuta en paralelo en múltiples workers.
#
# ¿Cómo funciona?
#   1. Beam lee un mensaje de Pub/Sub (bytes)
#   2. Lo pasa a ParseEvent.process(element)
#   3. process() lo transforma y hace yield del resultado
#   4. El resultado va a la siguiente PCollection
#
# ¿Por qué una clase y no una función?
#   Porque puede tener estado entre elementos:
#   - setup(): se ejecuta 1 vez al iniciar (ej: conectar a BD)
#   - process(): se ejecuta por cada elemento
#   - teardown(): se ejecuta 1 vez al cerrar (ej: cerrar conexión)
#
# AWS análogo:
#   Es como una función Lambda que procesa cada record de Kinesis.
#   Pero el DoFn es más eficiente — reutiliza la instancia entre
#   elementos en vez de crear/destruir por cada invocación.
#
# Ejemplo visual:
#   PCollection de entrada: [msg1, msg2, msg3, msg4, msg5]
#                              │      │      │      │      │
#                    Worker 1: DoFn  DoFn  DoFn
#                    Worker 2:              DoFn  DoFn
#                              │      │      │      │      │
#   PCollection de salida:   [dict1, dict2, dict3, dict4, dict5]
# ============================================

class ParseEvent(beam.DoFn):
    """
    DoFn que parsea el mensaje JSON de Pub/Sub y lo prepara para Bronze.

    Input:  bytes — mensaje crudo de Pub/Sub (ej: b'{"event_id":"rt-001",...}')
    Output: dict  — fila lista para BigQuery (ej: {"event_id":"rt-001", "raw_payload":"...", ...})

    Si el mensaje es inválido (no tiene event_id, JSON roto, etc.),
    NO hace yield → el elemento desaparece de la PCollection.
    En missing.md se explica cómo usar TaggedOutput para no perder estos elementos.
    """

    def process(self, element):
        """
        Se ejecuta por CADA mensaje de Pub/Sub.

        'element' es un bytes que viene de la PCollection anterior (ReadFromPubSub).
        'yield' produce un dict que va a la PCollection siguiente (WriteToBigQuery).
        'return' sin yield = el elemento se descarta (no pasa a la siguiente PCollection).

        Es como un map() con filtro:
          - Si el dato es válido → yield (pasa al siguiente paso)
          - Si el dato es inválido → return (se descarta)

        AWS análogo: el handler de una Lambda que procesa records de Kinesis.
          def handler(event, context):
              for record in event['Records']:
                  data = json.loads(record['kinesis']['data'])
                  # procesar...
        """
        try:
            # ── Paso 1: Decodificar bytes → string → dict ──
            # Pub/Sub envía mensajes como bytes. Necesitamos parsearlo a JSON.
            raw = element.decode("utf-8") if isinstance(element, bytes) else element
            event = json.loads(raw)

            # ── Paso 2: Validar campos requeridos ──
            # Si no tiene event_id o event_type, no sirve.
            event_id = event.get("event_id")
            event_type = event.get("event_type")

            if not event_id or not event_type:
                # return sin yield = el elemento se descarta de la PCollection.
                # El mensaje se pierde silenciosamente.
                # Con TaggedOutput (ver missing.md) iría a una tabla de errores.
                logging.warning(f"Evento sin event_id o event_type: {raw[:200]}")
                return

            # ── Paso 3: Producir el resultado ──
            # yield = produce un elemento en la PCollection de salida.
            # Este dict es exactamente una fila que BigQuery va a insertar.
            # Puede haber múltiples yields por cada input (1 input → N outputs).
            yield {
                "event_id": event_id,
                "event_type": event_type,
                # raw_payload guarda el JSON completo — Bronze nunca pierde datos.
                "raw_payload": json.dumps(event, ensure_ascii=False),
                "source": "streaming/pubsub",
                "ingested_at": datetime.now(timezone.utc).isoformat(),
            }

        except json.JSONDecodeError as e:
            # JSON roto → se descarta (no yield)
            logging.error(f"JSON inválido: {e}")
        except Exception as e:
            # Error inesperado → se descarta (no yield)
            logging.error(f"Error procesando evento: {e}")


# ============================================
# Pipeline — CONCEPTOS #1 (PCollection), #3 (Exactly-once), #4 (Auto-scaling)
#
# ¿Qué es un Pipeline?
#   El flujo completo de datos de principio a fin.
#   Es como una cadena de producción en una fábrica:
#     Materia prima (Pub/Sub) → Procesamiento (ParseEvent) → Producto final (BigQuery)
#
# AWS análogo:
#   Es como un Kinesis Data Analytics application, o un Glue ETL job,
#   o un Step Functions workflow — pero todo en un solo archivo Python.
#   La diferencia principal: Beam es un framework, no un servicio.
#   El servicio es Dataflow (que ejecuta Beam). Como Spark es framework
#   y EMR es el servicio que lo ejecuta.
#
# ¿Qué es el operador | (pipe)?
#   Conecta pasos del pipeline. Cada | produce una nueva PCollection.
#   "Read" | "Parse" | "Write" es como: tabla1 → transform → tabla2 en SQL.
#
# ¿Qué es >> ?
#   Asigna un nombre al paso. "Read from Pub/Sub" es el nombre que
#   aparece en el grafo visual de Dataflow en la consola de GCP.
# ============================================

def run():
    # ── Opciones del Pipeline ──
    # Se leen de los argumentos de CLI (--project, --runner, etc.)
    # AWS análogo: es como la configuración de un Glue job (DPUs, timeout, etc.)
    options = PipelineOptions()

    # ── Modo Streaming ──
    # streaming=True → el pipeline nunca termina. Espera mensajes continuamente.
    #                   Como un servidor web que nunca se apaga.
    # streaming=False → lee datos finitos, procesa, termina. Como un script batch.
    # AWS análogo: Kinesis Data Analytics siempre es streaming.
    #              Glue siempre es batch. Beam puede ser ambos.
    options.view_as(StandardOptions).streaming = True

    # ── Crear y ejecutar el Pipeline ──
    # 'with' asegura que p.run() se llame al salir del bloque.
    with beam.Pipeline(options=options) as p:
        (
            p

            # ═══════════════════════════════════════════════════════
            # PASO 1: Leer de Pub/Sub → PCollection de bytes
            # ═══════════════════════════════════════════════════════
            #
            # ReadFromPubSub:
            #   - Se conecta al topic "realtime-events"
            #   - Lee mensajes continuamente (streaming pull)
            #   - Cada mensaje es un elemento tipo bytes en la PCollection
            #   - NUNCA termina — siempre espera más mensajes
            #
            # PCollection #1 resultante:
            #   [b'{"event_id":"rt-001",...}', b'{"event_id":"rt-002",...}', ...]
            #   Tipo: PCollection[bytes]
            #   Tamaño: infinito (streaming)
            #
            # AWS análogo:
            #   GetRecords de un Kinesis Stream, o
            #   ReceiveMessage de SQS en un loop infinito.
            #   La diferencia: Beam abstrae el polling — tú solo
            #   dices "lee de aquí" y él se encarga del resto.
            #
            | "Read from Pub/Sub" >> beam.io.ReadFromPubSub(topic=TOPIC)

            # ═══════════════════════════════════════════════════════
            # PASO 2: Parsear → PCollection de dicts
            # ═══════════════════════════════════════════════════════
            #
            # ParDo (Parallel Do):
            #   - Toma cada bytes de la PCollection anterior
            #   - Lo pasa a ParseEvent.process()
            #   - El yield de process() produce un dict
            #   - Los elementos sin yield se descartan
            #
            # PCollection #2 resultante:
            #   [{"event_id":"rt-001", "event_type":"page_view", ...}, ...]
            #   Tipo: PCollection[dict]
            #   Tamaño: ≤ PCollection #1 (algunos se descartan)
            #
            # AWS análogo:
            #   Una función Lambda de transformación en un Kinesis Firehose,
            #   o un map() en Spark/Glue.
            #
            | "Parse Event" >> beam.ParDo(ParseEvent())

            # ═══════════════════════════════════════════════════════
            # PASO 3: Escribir en BigQuery Bronze (Sink)
            # ═══════════════════════════════════════════════════════
            #
            # WriteToBigQuery:
            #   - Consume cada dict de la PCollection
            #   - Lo inserta como una fila en la tabla bronze.events_raw
            #
            # STREAMING_INSERTS (método de escritura):
            #   - Inserta fila por fila en tiempo real (~1-3 seg de latencia)
            #   - Más caro que LOAD_JOBS pero más rápido
            #   - LOAD_JOBS acumula filas y las carga en batch (más barato, ~minutos)
            #   - Para streaming, STREAMING_INSERTS es la opción correcta
            #
            # WRITE_APPEND:
            #   - Agrega filas a la tabla existente (no la reemplaza)
            #   - Otras opciones: WRITE_TRUNCATE (borra y reescribe), WRITE_EMPTY (solo si vacía)
            #
            # CREATE_NEVER:
            #   - La tabla DEBE existir antes (creada por Terraform)
            #   - Si no existe → error. Esto es intencional — no queremos que
            #     Dataflow cree tablas con esquemas adivinados.
            #
            # Exactly-once (#3):
            #   Dataflow + STREAMING_INSERTS garantizan que cada evento
            #   se escribe EXACTAMENTE UNA VEZ en BigQuery:
            #   - Si un worker muere después de leer pero antes de escribir
            #     → Dataflow reintenta en otro worker
            #   - Si un worker escribe pero muere antes de confirmar
            #     → Dataflow detecta el duplicado con IDs internos y no lo reescribe
            #   - No necesitas código — es una propiedad del runtime
            #   AWS: Kinesis + Lambda es "at-least-once" (puede duplicar).
            #         Para exactly-once necesitas DynamoDB como tabla de deduplicación.
            #         Dataflow lo hace automáticamente sin tabla extra.
            #
            # AWS análogo del sink completo:
            #   Kinesis Firehose → S3/Redshift, o
            #   Lambda → DynamoDB/RDS put_item.
            #   La diferencia: WriteToBigQuery maneja batching, reintentos,
            #   backpressure y exactly-once automáticamente.
            #
            | "Write to Bronze" >> WriteToBigQuery(
                table=BRONZE_TABLE,
                schema=BRONZE_SCHEMA,
                write_disposition=BigQueryDisposition.WRITE_APPEND,
                create_disposition=BigQueryDisposition.CREATE_NEVER,
                method="STREAMING_INSERTS",
            )
        )


if __name__ == "__main__":
    logging.getLogger().setLevel(logging.INFO)
    run()
