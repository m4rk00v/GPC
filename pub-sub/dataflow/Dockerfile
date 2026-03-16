# ============================================
# Dockerfile — Flex Template para Dataflow
#
# Usa la imagen oficial de Dataflow Flex Template que incluye
# el launcher (/opt/google/dataflow/python_template_launcher)
# necesario para que Dataflow ejecute el pipeline.
#
# La imagen apache/beam_python_sdk NO tiene el launcher —
# solo sirve para correr pipelines con el CLI, no como Flex Template.
# ============================================

# Imagen base: Dataflow Flex Template para Python 3.12.  
# Incluye: Beam SDK + launcher + dependencias de GCP
FROM gcr.io/dataflow-templates-base/python312-template-launcher-base:latest

# Copiar dependencias e instalar
COPY requirements.txt /template/requirements.txt
RUN pip install --no-cache-dir -r /template/requirements.txt

# Copiar el código del pipeline
COPY streaming_pipeline.py /template/streaming_pipeline.py

# Variable de entorno: indicar dónde está el pipeline
# El launcher de Flex Template lee esta variable para saber qué ejecutar
ENV FLEX_TEMPLATE_PYTHON_PY_FILE="/template/streaming_pipeline.py"

# Requerimientos del pipeline (Beam los instala en los workers)
ENV FLEX_TEMPLATE_PYTHON_REQUIREMENTS_FILE="/template/requirements.txt"
