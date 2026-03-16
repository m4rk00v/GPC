# Cloud Run + Cloud Scheduler — Exponer y orquestar servicios

## Qué es Cloud Run

Ejecuta contenedores Docker sin administrar servidores. Escala a 0 cuando no hay tráfico (no pagas).

| Concepto | Cloud Run | AWS análogo |
|---|---|---|
| Service (HTTP) | Contenedor que responde requests | Lambda / Fargate |
| Job (batch) | Contenedor que corre y termina | AWS Batch / ECS Task |
| Scheduler | Trigger por cron | EventBridge Scheduler |
| Registry | Artifact Registry | ECR |

---

## Los 10 conceptos

### 1. Cloud Run Service — Contenedor HTTP

Despliega un contenedor que recibe requests HTTP y responde. Escala automáticamente.

```
Request HTTP → Cloud Run → tu contenedor responde → respuesta al cliente
Sin requests → escala a 0 instancias → no pagas
```

**En nuestro E-commerce:** API que expone datos de Gold (dashboard, métricas).

```bash
gcloud run deploy ecommerce-api \
  --image=europe-west1-docker.pkg.dev/project-dev-490218/cloud-run/ecommerce-api:latest \
  --region=europe-west1 \
  --service-account=sa-cloudrun@project-dev-490218.iam.gserviceaccount.com \
  --no-allow-unauthenticated \
  --min-instances=0 \
  --max-instances=5 \
  --memory=512Mi \
  --timeout=60
```

> **Buena práctica:** Configurar health checks — `/health` endpoint que GCP usa para saber si el servicio está vivo.
> **Problema que evitas:** GCP redirige tráfico a instancias que están iniciando y aún no están listas.

Health check en tu app:

```python
@app.get("/health")
def health():
    return {"status": "ok"}
```

---

### 2. Cloud Run Job — Contenedor batch

A diferencia del Service (siempre escuchando), un Job **corre una vez y termina**.

```
Scheduler dispara → Cloud Run Job arranca → ejecuta tarea → termina → no cobra más
```

**En nuestro E-commerce:** Ejecutar Bronze → Silver (alternativa a Composer, más barata).

```bash
gcloud run jobs create bronze-to-silver \
  --image=europe-west1-docker.pkg.dev/project-dev-490218/cloud-run/bronze-to-silver:latest \
  --region=europe-west1 \
  --service-account=sa-functions@project-dev-490218.iam.gserviceaccount.com \
  --memory=1Gi \
  --task-timeout=600 \
  --max-retries=3
```

> **Buena práctica:** Usar Job para pipelines batch — no Service que está siempre activo.
> **Problema que evitas:** Pagar por un servicio HTTP activo 24/7 cuando solo lo necesitas 1 vez al día.

| Cuándo usar | Service | Job |
|---|---|---|
| API HTTP (requests todo el día) | Sí | No |
| Pipeline batch (1 vez al día) | No | Sí |
| Webhook (cuando alguien lo llama) | Sí | No |
| ETL programado (Bronze → Silver) | No | Sí |

---

### 3. Dockerfile — Empaquetar la app

```dockerfile
# Imagen base mínima — python:3.12-slim es ~150MB
# python:3.12 completo es ~1GB — 7x más grande
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Cloud Run requiere que escuches en $PORT (default 8080)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

> **Buena práctica:** Usar imágenes base mínimas (`python:3.12-slim`) — reducen build time y superficie de ataque.
> **Problema que evitas:** Imagen de 2GB que tarda 10 min en pull en cada cold start.

| Imagen | Tamaño | Cold start |
|---|---|---|
| `python:3.12` | ~1 GB | ~10 seg |
| `python:3.12-slim` | ~150 MB | ~3 seg |
| `python:3.12-alpine` | ~50 MB | ~2 seg (pero problemas con algunas libs) |

---

### 4. Artifact Registry — Repositorio de imágenes

Donde guardas las imágenes Docker. Como ECR en AWS.

```bash
# Crear repositorio
gcloud artifacts repositories create cloud-run --repository-format=docker --location=europe-west1

# Build y push
docker build -t europe-west1-docker.pkg.dev/project-dev-490218/cloud-run/ecommerce-api:latest .
docker push europe-west1-docker.pkg.dev/project-dev-490218/cloud-run/ecommerce-api:latest
```

> **Buena práctica:** Configurar vulnerability scanning automático en Artifact Registry.
> **Problema que evitas:** Imagen con librerías vulnerables desplegada en producción sin que nadie lo sepa.

```bash
# Habilitar scanning
gcloud artifacts repositories update cloud-run \
  --location=europe-west1 \
  --remote-apt-repo-config-desc="Enable vulnerability scanning"
```

---

### 5. `--no-allow-unauthenticated` — Solo requests autenticados

```bash
# CORRECTO — solo acepta requests con token válido
gcloud run deploy ecommerce-api --no-allow-unauthenticated

# PELIGROSO — cualquiera en internet puede llamar tu API
gcloud run deploy ecommerce-api --allow-unauthenticated
```

> **Buena práctica:** Siempre `--no-allow-unauthenticated`. Solo autenticar explícitamente lo público.
> **Problema que evitas:** Endpoint interno expuesto públicamente accesible sin credenciales.

| Cuándo `--allow-unauthenticated` | Cuándo `--no-allow-unauthenticated` |
|---|---|
| Landing page pública | API interna |
| Webhook que recibe de terceros | Pipeline que solo llama Scheduler |
| Nunca para endpoints con datos | Siempre por defecto |

---

### 6. OIDC Token — Scheduler llama a Cloud Run

Cloud Scheduler necesita un token para autenticarse con Cloud Run.
GCP genera un token OIDC (OpenID Connect) automáticamente.

```bash
# Scheduler llama a Cloud Run con token OIDC
gcloud scheduler jobs create http bronze-to-silver-trigger \
  --schedule="*/3 * * * *" \
  --uri="https://ecommerce-api-xxxx-ew.a.run.app/trigger-etl" \
  --http-method=POST \
  --oidc-service-account-email=sa-scheduler@project-dev-490218.iam.gserviceaccount.com \
  --oidc-token-audience="https://ecommerce-api-xxxx-ew.a.run.app" \
  --location=europe-west1 \
  --time-zone="America/Mexico_City"
```

> **Buena práctica:** Verificar el token OIDC en el handler — no confiar solo en GCP.
> **Problema que evitas:** Request no autorizado que llega al endpoint porque alguien conoce la URL.

---

### 7. Cloud Scheduler — Trigger por cron

Ejecuta una acción en un horario definido. Como EventBridge Scheduler en AWS.

```bash
# Cada 3 minutos
gcloud scheduler jobs create http my-job --schedule="*/3 * * * *" ...

# Todos los días a las 3am hora de México
gcloud scheduler jobs create http my-job --schedule="0 3 * * *" --time-zone="America/Mexico_City" ...
```

> **Buena práctica:** Configurar timezone explícitamente — por defecto es UTC.
> **Problema que evitas:** Job que corre a las 3am UTC cuando esperabas las 3am hora de Santiago.

---

### 8. Cron syntax

```
┌───────── minuto (0-59)
│ ┌─────── hora (0-23)
│ │ ┌───── día del mes (1-31)
│ │ │ ┌─── mes (1-12)
│ │ │ │ ┌─ día de la semana (0-6, 0=domingo)
│ │ │ │ │
* * * * *
```

| Expresión | Significa |
|---|---|
| `*/3 * * * *` | Cada 3 minutos |
| `0 * * * *` | Cada hora (minuto 0) |
| `0 3 * * *` | Todos los días a las 3am |
| `0 6 * * 1` | Cada lunes a las 6am |
| `0 0 1 * *` | Primer día de cada mes a medianoche |

> **Buena práctica:** Validar en crontab.guru antes de configurar.
> **Problema que evitas:** Cron mal configurado que corre cada minuto en lugar de cada hora.

---

### 9. Concurrency — Requests simultáneos

Cuántas requests puede manejar una instancia al mismo tiempo.

```bash
# Para API (múltiples requests simultáneos OK)
gcloud run deploy ecommerce-api --concurrency=80

# Para jobs batch (NO deben correr en paralelo)
gcloud run deploy bronze-to-silver --concurrency=1
```

> **Buena práctica:** `--concurrency=1` para jobs que no deben correr en paralelo.
> **Problema que evitas:** Dos ejecuciones simultáneas del mismo pipeline que escriben los mismos datos en BigQuery.

| Escenario | Concurrency |
|---|---|
| API HTTP (stateless) | 80 (default) |
| Pipeline batch (escribe en BQ) | 1 |
| Webhook (procesa un evento) | 10-20 |

---

### 10. Cold Start — Primera ejecución tarda más

Cuando no hay instancias activas, Cloud Run crea una nueva al recibir un request. Eso tarda.

```
Request llega → No hay instancia → Pull imagen → Iniciar contenedor → Responder
                                    └── cold start: 2-30 segundos ──┘
```

```bash
# Sin min-instances (barato pero cold start)
gcloud run deploy ecommerce-api --min-instances=0

# Con min-instances (siempre 1 lista, sin cold start pero cuesta ~$15/mes)
gcloud run deploy ecommerce-api --min-instances=1
```

> **Buena práctica:** `--min-instances=1` para servicios críticos de baja latencia.
> **Problema que evitas:** Primera request del día tarda 30 seg porque el contenedor debe iniciar desde cero.

| Config | Cold start | Costo |
|---|---|---|
| `--min-instances=0` | Sí (2-30 seg) | Solo pagas cuando hay tráfico |
| `--min-instances=1` | No | ~$15/mes (1 instancia siempre activa) |

---

## Cómo se conecta con nuestro E-commerce

```
┌─────────────────────────────────────────────────────────┐
│                                                         │
│  Cloud Run SERVICE — API del E-commerce                 │
│  ├── GET  /health                   → health check      │
│  ├── GET  /api/metrics/revenue      → gold.daily_revenue│
│  ├── GET  /api/metrics/customers    → gold.customer_metrics│
│  ├── GET  /api/metrics/funnel       → gold.conversion_funnel│
│  ├── POST /api/events               → Pub/Sub realtime  │
│  └── POST /trigger-etl              → dispara MERGE     │
│                                                         │
│  Cloud Run JOB — ETL Bronze → Silver                    │
│  └── Corre MERGE queries (alternativa barata a Composer)│
│                                                         │
│  Cloud Scheduler                                        │
│  ├── */3 * * * * → POST /trigger-etl (cada 3 min)      │
│  └── 0 3 * * *   → Ejecutar Cloud Run Job (3am diario) │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### Cloud Run + Scheduler como alternativa a Composer

| Aspecto | Composer (Airflow) | Cloud Run Job + Scheduler |
|---|---|---|
| Costo | ~$300/mes | ~$1-5/mes |
| Orquestación visual | Sí (DAG UI) | No |
| Dependencias entre tasks | Sí | No (secuencial manual) |
| Para nuestro caso | Overkill | Suficiente |

---

## Pasos para implementar

| Paso | Qué |
|---|---|
| 1 | `gcloud services enable run.googleapis.com cloudscheduler.googleapis.com` |
| 2 | Crear Dockerfile de la API |
| 3 | Build + push imagen a Artifact Registry |
| 4 | Deploy Cloud Run Service (`--no-allow-unauthenticated`) |
| 5 | Configurar Cloud Scheduler con OIDC token |
| 6 | Crear Cloud Run Job para ETL (opcional — alternativa a Composer) |
| 7 | Definir en Terraform (`infra/cloud-run/`) |

---

## Costos

| Componente | Precio |
|---|---|
| Cloud Run (por request) | $0.40/millón de requests |
| Cloud Run (CPU) | $0.00002400/vCPU-segundo |
| Cloud Run (memoria) | $0.00000250/GiB-segundo |
| Cloud Scheduler | $0.10/job/mes |
| **Estimado E-commerce (bajo tráfico)** | **~$1-5/mes** |
| **vs Composer** | **~$300/mes** |
