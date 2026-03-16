"""
Cloud Function: ingest-csv
Trigger: Pub/Sub topic "csv-uploaded" (disparado por Cloud Storage OBJECT_FINALIZE)

Flujo:
1. Cloud Storage notifica que un CSV fue subido
2. Pub/Sub entrega el mensaje a esta function
3. La function lee el CSV del bucket
4. Detecta la tabla Bronze por la carpeta del archivo
5. Parsea cada fila como JSON y la inserta en BigQuery Bronze
6. ACK automático si no hay excepciones

Buenas prácticas implementadas:
- Esquema explícito (no autodetect)
- JSON crudo en raw_data (Bronze nunca parsea, solo almacena)
- Validación de archivo (.csv)
- Validación de carpeta (solo las conocidas)
- Logging estructurado para debugging
- Batch insert para performance
"""

import json
import csv
import io
import os
from datetime import datetime, timezone

import functions_framework
from google.cloud import bigquery, storage

# ============================================
# Configuración
# ============================================

# Mapeo: carpeta del bucket → tabla Bronze en BigQuery
# Si subes un CSV a gs://bucket/customers/data.csv → inserta en bronze.customers_raw
FOLDER_TO_TABLE = {
    "customers": "customers_raw",
    "products": "products_raw",
    "orders": "orders_raw",
    "order_items": "order_items_raw",
    "payments": "payments_raw",
    "events": "events_raw",
    "inventory": "inventory_raw",
    "reviews": "reviews_raw",
}

# Dataset Bronze en BigQuery
BRONZE_DATASET = "bronze"

# Proyecto GCP (se lee de variable de entorno para no hardcodear)
PROJECT_ID = os.environ.get("GCP_PROJECT", "project-dev-490218")

# Clientes de GCP (se inicializan una vez fuera de la function para reutilizar entre invocaciones)
bq_client = bigquery.Client(project=PROJECT_ID)
storage_client = storage.Client(project=PROJECT_ID)


# ============================================
# Entry point — Pub/Sub trigger (Gen2)
# ============================================

@functions_framework.cloud_event
def ingest_csv(cloud_event):
    """
    Cloud Function triggered by Pub/Sub message.
    Gen2 usa CloudEvents, no el formato legacy de Gen1.

    El mensaje de Pub/Sub contiene los datos de la notificación de Cloud Storage:
    - bucket: nombre del bucket
    - name: path del archivo (ej: "customers/data.csv")
    - size: tamaño en bytes
    - contentType: tipo MIME
    """

    # ---- 1. Decodificar el mensaje de Pub/Sub ----
    data = cloud_event.data
    message_data = data.get("message", {}).get("data", "")

    if isinstance(message_data, str):
        import base64
        message = json.loads(base64.b64decode(message_data).decode("utf-8"))
    else:
        message = message_data

    bucket_name = message.get("bucket", "")
    file_name = message.get("name", "")

    print(f"[INFO] Evento recibido: gs://{bucket_name}/{file_name}")

    # ---- 2. Validar que es un CSV ----
    if not file_name.endswith(".csv"):
        print(f"[SKIP] Ignorando {file_name} — no es un archivo CSV")
        return

    # Ignorar archivos .keep (usados para crear carpetas)
    if file_name.endswith(".keep"):
        print(f"[SKIP] Ignorando {file_name} — archivo .keep")
        return

    # ---- 3. Detectar la tabla Bronze por la carpeta ----
    # El archivo está en "customers/data.csv" → carpeta = "customers"
    folder = file_name.split("/")[0]
    table_name = FOLDER_TO_TABLE.get(folder)

    if not table_name:
        print(f"[ERROR] Carpeta desconocida: '{folder}'. Carpetas válidas: {list(FOLDER_TO_TABLE.keys())}")
        return

    print(f"[INFO] Carpeta: {folder} → Tabla: {BRONZE_DATASET}.{table_name}")

    # ---- 4. Leer el CSV de Cloud Storage ----
    try:
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(file_name)
        content = blob.download_as_text(encoding="utf-8")
    except Exception as e:
        print(f"[ERROR] No se pudo leer gs://{bucket_name}/{file_name}: {e}")
        raise  # Re-raise para que Pub/Sub reintente

    # ---- 5. Parsear CSV y preparar filas para Bronze ----
    reader = csv.DictReader(io.StringIO(content))
    rows = []
    now = datetime.now(timezone.utc).isoformat()

    for line_num, row in enumerate(reader, start=1):
        try:
            if folder == "events":
                # Events tiene esquema distinto: event_id, event_type, raw_payload
                rows.append({
                    "event_id": row.get("event_id", f"ev-auto-{line_num}"),
                    "event_type": row.get("event_type", "unknown"),
                    "raw_payload": json.dumps(row, ensure_ascii=False),
                    "source": f"gcs/{file_name}",
                    "ingested_at": now,
                })
            else:
                # Todas las demás tablas: record_id, raw_data (JSON crudo)
                # record_id = primer campo del CSV (id, order_id, payment_id, etc.)
                record_id = next(iter(row.values()), f"auto-{line_num}")
                rows.append({
                    "record_id": str(record_id),
                    "raw_data": json.dumps(row, ensure_ascii=False),
                    "source": f"gcs/{file_name}",
                    "ingested_at": now,
                })
        except Exception as e:
            print(f"[WARN] Error parseando línea {line_num}: {e}")
            continue  # Saltar filas con errores, no fallar todo el CSV

    if not rows:
        print(f"[WARN] CSV vacío o sin filas válidas: {file_name}")
        return

    # ---- 6. Insertar en BigQuery Bronze ----
    table_ref = bq_client.dataset(BRONZE_DATASET).table(table_name)

    try:
        errors = bq_client.insert_rows_json(table_ref, rows)
    except Exception as e:
        print(f"[ERROR] Fallo insertando en {BRONZE_DATASET}.{table_name}: {e}")
        raise  # Re-raise para que Pub/Sub reintente

    # ---- 7. Reportar resultado ----
    if errors:
        print(f"[ERROR] Errores de BigQuery en {BRONZE_DATASET}.{table_name}: {errors}")
        # No raise — las filas que sí se insertaron están bien
        # Los errores típicos son por esquema (campo faltante, tipo incorrecto)
    else:
        print(f"[OK] Insertadas {len(rows)} filas en {BRONZE_DATASET}.{table_name} desde {file_name}")
