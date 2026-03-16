"""
Dataflow Streaming Pipeline: Pub/Sub → BigQuery Bronze

Lee eventos en tiempo real de Pub/Sub,
los valida, parsea y escribe en BigQuery Bronze.

Ejecutar en Dataflow:
  python streaming_pipeline.py \
    --project=project-dev-490218 \
    --region=europe-west1 \
    --runner=DataflowRunner \
    --temp_location=gs://project-dev-490218-dataflow-temp/tmp \
    --staging_location=gs://project-dev-490218-dataflow-temp/staging \
    --streaming \
    --service_account_email=sa-functions@project-dev-490218.iam.gserviceaccount.com \
    --max_num_workers=2 \
    --machine_type=n1-standard-1

Ejecutar local (testing):
  python streaming_pipeline.py --runner=DirectRunner --streaming
"""

import json
import logging
from datetime import datetime

import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions, StandardOptions
from apache_beam.io.gcp.bigquery import WriteToBigQuery, BigQueryDisposition


# ============================================
# Configuración
# ============================================

PROJECT_ID = "project-dev-490218"
TOPIC = f"projects/{PROJECT_ID}/topics/realtime-events"
BRONZE_TABLE = f"{PROJECT_ID}:bronze.events_raw"

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
# Transforms
# ============================================

class ParseEvent(beam.DoFn):
    """Parsea el mensaje JSON de Pub/Sub y lo prepara para Bronze."""

    def process(self, element):
        try:
            raw = element.decode("utf-8") if isinstance(element, bytes) else element
            event = json.loads(raw)

            event_id = event.get("event_id")
            event_type = event.get("event_type")

            if not event_id or not event_type:
                logging.warning(f"Evento sin event_id o event_type: {raw[:200]}")
                return

            yield {
                "event_id": event_id,
                "event_type": event_type,
                "raw_payload": json.dumps(event, ensure_ascii=False),
                "source": "streaming/pubsub",
                "ingested_at": datetime.utcnow().isoformat(),
            }

        except json.JSONDecodeError as e:
            logging.error(f"JSON inválido: {e}")
        except Exception as e:
            logging.error(f"Error procesando evento: {e}")


# ============================================
# Pipeline
# ============================================

def run():
    options = PipelineOptions()
    options.view_as(StandardOptions).streaming = True

    with beam.Pipeline(options=options) as p:
        (
            p
            | "Read from Pub/Sub" >> beam.io.ReadFromPubSub(topic=TOPIC)
            | "Parse Event" >> beam.ParDo(ParseEvent())
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
