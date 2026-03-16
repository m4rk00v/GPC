# ============================================
# Dockerfile — Flex Template para Dataflow
#
# Empaqueta el pipeline streaming_pipeline.py
# en un container Docker que Dataflow ejecuta.
#
# Build:
#   docker build -t europe-west1-docker.pkg.dev/project-dev-490218/dataflow/streaming-pipeline:latest .  
#
# Push:
#   docker push europe-west1-docker.pkg.dev/project-dev-490218/dataflow/streaming-pipeline:latest.  
# ============================================

# Imagen base: Apache Beam SDK para Python 3.12
# Incluye Beam + dependencias de GCP preinstaladas.       
FROM apache/beam_python3.12_sdk:2.71.0

# Copiar dependencias e instalar
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copiar el código del pipeline
COPY streaming_pipeline.py /app/streaming_pipeline.py

# Variable de entorno: indicar dónde está el pipeline
ENV FLEX_TEMPLATE_PYTHON_PY_FILE="/app/streaming_pipeline.py"
