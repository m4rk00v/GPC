# Explorar la Consola GCP (15 min)

## Paso 1 — Acceder a la consola (2 min)

- Ve a console.cloud.google.com
- Arriba a la izquierda verifica que estés en el proyecto **project-dev-490218**
- Si no, haz clic en el selector de proyectos y cámbialo

## Paso 2 — Recorrido por el menú principal (5 min)

Abre el menú hamburguesa (☰) y recorre estas secciones clave:

| Sección | Análogo AWS | Para qué la usarás |
|---|---|---|
| **Compute Engine** | EC2 | Máquinas virtuales |
| **Cloud Run** | ECS Fargate | Contenedores serverless |
| **GKE (Kubernetes Engine)** | EKS | Orquestación de contenedores |
| **Cloud SQL** | RDS | Bases de datos administradas |
| **Cloud Storage** | S3 | Almacenamiento de objetos |
| **Secret Manager** | Secrets Manager | Credenciales y secretos |
| **IAM & Admin** | IAM | Permisos y roles |
| **Billing** | Cost Explorer | Costos y alertas |
| **APIs & Services** | Service Quotas | APIs habilitadas y cuotas |

## Paso 3 — Abrir Cloud Shell (3 min)

- En la barra superior, haz clic en el ícono de terminal **`>_`** (esquina superior derecha)
- Se abrirá una terminal en el navegador con `gcloud` preinstalado
- Prueba estos comandos:

```bash
gcloud config get project
gcloud services list --enabled
whoami
```

- Cloud Shell tiene 5 GB de almacenamiento persistente en `$HOME`
- Se apaga tras 20 min de inactividad (no pierdes archivos)

## Paso 4 — Comparar Cloud Shell vs tu CLI local (3 min)

Corre esto en **Cloud Shell** y en tu **terminal local** para ver diferencias:

```bash
gcloud version
```

| Aspecto | CLI Local | Cloud Shell |
|---|---|---|
| Versión | La que instalaste | Siempre actualizada por Google |
| Autenticación | `gcloud auth login` | Ya autenticada |
| Persistencia | Tu máquina | Solo `$HOME` persiste |
| Acceso red interna GCP | No (va por internet) | Sí (está dentro de GCP) |

## Paso 5 — Verificar APIs habilitadas (2 min)

- Menú → **APIs & Services** → **Enabled APIs**
- Verifica que aparezcan las que habilitaste con el comando anterior
