# Secret Manager — Plan de Acción

## Qué es

Secret Manager almacena credenciales, API keys, passwords y configuraciones sensibles de forma encriptada. Los servicios los leen en tiempo de ejecución — nunca se hardcodean en el código.

## Cómo funciona

```
Developer                Secret Manager              Cloud Run / Functions
─────────               ──────────────              ────────────────────
Crea el secreto    →    Almacena encriptado
Agrega versión     →    Guarda el valor
                        SA con rol                →  Lee el secreto en runtime
                        secretAccessor                via variable de entorno
```

---

## Paso 1 — Definir los secretos en Terraform

Los secretos se definen en `infra/secrets.tf`. Terraform crea el **contenedor** (nombre del secreto), pero **NO el valor**.

> **Los valores NUNCA van en archivos .tf** porque se versionan en Git.

### Secretos del stack completo

| Secreto | Para qué | Quién lo consume |
|---|---|---|
| `db-password` | Password de Cloud SQL | sa-cloudrun, sa-functions |
| `db-host` | Host/IP de Cloud SQL | sa-cloudrun, sa-functions |
| `db-name` | Nombre de la base de datos | sa-cloudrun, sa-functions |
| `db-user` | Usuario de la base de datos | sa-cloudrun, sa-functions |
| `redis-url` | URL de conexión a Redis | sa-cloudrun |
| `api-key` | API key de la aplicación | sa-cloudrun |
| `jwt-secret` | Secret para firmar tokens JWT | sa-cloudrun |
| `smtp-password` | Password del servicio de email | sa-cloudrun, sa-functions |
| `webhook-secret` | Secret para validar webhooks | sa-cloudrun |
| `storage-bucket` | Nombre del bucket principal | sa-cloudrun, sa-functions |

### Estado actual

Ya existen en `secrets.tf`: `db-password`, `db-host`, `redis-url`, `api-key`

Faltan por agregar: `db-name`, `db-user`, `jwt-secret`, `smtp-password`, `webhook-secret`, `storage-bucket`

---

## Paso 2 — Actualizar secrets.tf y hacer push

1. Agregar los 6 secretos faltantes en `infra/secrets.tf`
2. Hacer push → el pipeline crea los secretos en GCP

---

## Paso 3 — Agregar valores a los secretos

Esto se hace **manualmente** desde la terminal, **nunca en Terraform**.

```bash
# Base de datos
echo -n "tu-password-seguro" | gcloud secrets versions add db-password --data-file=-
echo -n "10.0.0.1" | gcloud secrets versions add db-host --data-file=-
echo -n "continuum_db" | gcloud secrets versions add db-name --data-file=-
echo -n "app_user" | gcloud secrets versions add db-user --data-file=-

# Redis
echo -n "redis://10.0.0.2:6379" | gcloud secrets versions add redis-url --data-file=-

# Aplicación
echo -n "tu-api-key-segura" | gcloud secrets versions add api-key --data-file=-
echo -n "tu-jwt-secret-largo-y-aleatorio" | gcloud secrets versions add jwt-secret --data-file=-
echo -n "tu-webhook-secret" | gcloud secrets versions add webhook-secret --data-file=-

# Email
echo -n "tu-smtp-password" | gcloud secrets versions add smtp-password --data-file=-

# Storage
echo -n "project-dev-490218-storage" | gcloud secrets versions add storage-bucket --data-file=-
```

> **Nota:** Los valores de arriba son ejemplos. Usa valores reales cuando tengas
> la infraestructura (Cloud SQL, Redis, etc.) creada.

---

## Paso 4 — Verificar los secretos

```bash
# Listar todos los secretos
gcloud secrets list

# Ver el valor de un secreto específico
gcloud secrets versions access latest --secret=db-password

# Ver las versiones de un secreto
gcloud secrets versions list db-password
```

---

## Paso 5 — Permisos (ya configurados)

Los permisos ya están definidos en `infra/iam.tf`:

| SA | Rol | Puede hacer |
|---|---|---|
| `sa-cloudrun` | `roles/secretmanager.secretAccessor` | Leer todos los secretos |
| `sa-functions` | `roles/secretmanager.secretAccessor` | Leer todos los secretos |
| `sa-pipeline` | `roles/secretmanager.admin` | Crear/administrar secretos (via Terraform) |

> **Mejora futura:** En producción se puede restringir el acceso por secreto
> individual en vez de dar acceso a todos. Ejemplo: sa-functions solo puede
> leer db-* y smtp-*, no jwt-secret ni webhook-secret.

---

## Paso 6 — Cómo Cloud Run / Functions leen los secretos

Cuando configuremos Cloud Run, los secretos se inyectan como variables de entorno:

```bash
# Ejemplo: desplegar un servicio que lee secretos
gcloud run deploy mi-servicio \
  --set-secrets="DB_PASSWORD=db-password:latest,DB_HOST=db-host:latest,REDIS_URL=redis-url:latest"
```

En Terraform se verá así:

```hcl
resource "google_cloud_run_v2_service" "app" {
  template {
    containers {
      env {
        name = "DB_PASSWORD"
        value_source {
          secret_key_ref {
            secret  = "db-password"
            version = "latest"
          }
        }
      }
    }
  }
}
```

---

## Paso 7 — Rotación de secretos

Cuando necesites cambiar un valor:

```bash
# Agregar nueva versión (el servicio usa "latest" automáticamente)
echo -n "nuevo-password" | gcloud secrets versions add db-password --data-file=-

# Si algo falla, rollback a la versión anterior
gcloud secrets versions access 1 --secret=db-password
```

Cada cambio crea una nueva **versión**. Los servicios que usan `:latest` obtienen el valor nuevo automáticamente al reiniciarse.

---

## Resumen — Orden de ejecución

| Paso | Qué | Cuándo |
|---|---|---|
| 1 | Definir secretos en `secrets.tf` | Ahora |
| 2 | Push → pipeline crea los contenedores | Ahora |
| 3 | Agregar valores manualmente con `gcloud` | Cuando tengas los valores reales |
| 4 | Verificar que existen | Después del paso 3 |
| 5 | Permisos | Ya hecho en iam.tf |
| 6 | Inyectar en Cloud Run / Functions | Cuando configuremos esos servicios |
| 7 | Rotación | Cuando necesites cambiar un valor |

---

## Errores comunes

| Error | Causa | Solución |
|---|---|---|
| `PERMISSION_DENIED` al leer un secreto | La SA no tiene `secretAccessor` | Verificar roles en `iam.tf` |
| `NOT_FOUND` al acceder un secreto | El secreto no existe o no tiene versiones | Verificar con `gcloud secrets list` y agregar versión |
| Valor vacío en la app | Se creó el secreto pero no se agregó valor | Correr `gcloud secrets versions add` |
