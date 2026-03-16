# Cloud DLP — Protección de PII (GDPR) en el E-commerce

## Qué es

Servicio de GCP que detecta y protege datos personales (PII) automáticamente.

| Cloud DLP | AWS análogo |
|---|---|
| Detectar PII | Amazon Macie |
| Transformar PII | Macie + Lambda custom |
| Claves de cifrado | AWS KMS |

---

## Los 9 conceptos

### 1. InfoTypes — Qué detectar

Solo los que necesitamos (no los 150 disponibles):

| InfoType | Detecta | Acción |
|---|---|---|
| `EMAIL_ADDRESS` | maria@example.com | Tokenizar (reversible) |
| `PHONE_NUMBER` | +1234567890 | Masking *** (irreversible) |
| `PERSON_NAME` | Maria Garcia | Tokenizar (reversible) |
| `STREET_ADDRESS` | Reforma 123 | Generalizar a ciudad |
| `CREDIT_CARD_NUMBER` | 4111...1111 | Masking ****1234 |
| `IP_ADDRESS` | 192.168.1.45 | Generalizar a /24 |

> **Buena práctica:** Solo los InfoTypes necesarios — cada uno extra suma latencia y costo.

### 2. Inspect — Detectar PII

Escanea Bronze y reporta dónde hay PII. No transforma nada.

```bash
gcloud dlp inspect-content \
  --content="Mi email es maria@example.com y tel +1234567890" \
  --info-types="EMAIL_ADDRESS,PHONE_NUMBER" \
  --min-likelihood=LIKELY
```

> **Buena práctica:** Inspeccionar en Bronze ANTES de transformar a Silver.

### 3. Deidentify — Transformar el PII

Toma el PII detectado y lo protege. Tres técnicas:

### 4. Character Masking — Reemplazar con ***

```
maria@example.com  →  m****@*******.com     (irreversible)
+1234567890        →  +*********0            (irreversible)
4111111111111111   →  ************1111       (irreversible)
```

> **Usar para:** PII que nunca necesitarás recuperar (teléfono, tarjeta de crédito).
> **No usar para:** Datos sujetos a derecho de acceso GDPR.

### 5. Tokenización FPE — Token reversible

```
maria@example.com  →  Xk9mP2qR5tW8          (reversible con clave KMS)
Maria Garcia       →  Hj3nL7vB4cY6          (reversible con clave KMS)
```

> **Usar para:** Datos que el usuario puede pedir ver (derecho de acceso GDPR).
> El mismo input siempre da el mismo token → permite JOINs entre tablas.

### 6. Generalización — Reducir precisión

```
Reforma 123, CDMX  →  CDMX, MX              (solo ciudad)
1990-05-15         →  1990                   (solo año)
192.168.1.45       →  192.168.1.0/24         (subnet)
```

> **Usar para:** Datos donde la precisión exacta no es necesaria para analytics.

### 7. Likelihood — Confianza de detección

| Nivel | Usar en producción |
|---|---|
| POSSIBLE | No — demasiados falsos positivos |
| **LIKELY** | **Sí — mínimo recomendado** |
| VERY_LIKELY | Sí — más estricto, menos falsos positivos |

> **Buena práctica:** LIKELY como mínimo. POSSIBLE enmascara texto normal que parece un nombre.

### 8. Integración en Dataflow — DLP dentro del DoFn

```python
class DeidentifyEvent(beam.DoFn):
    def setup(self):
        # UNA VEZ por worker — no por cada mensaje
        # Si lo pones en process() agotas el rate limit de la API
        self.dlp_client = dlp_v2.DlpServiceClient()

    def process(self, element):
        response = self.dlp_client.deidentify_content(...)
        element["raw_payload"] = response.item.value
        yield element
```

> **Buena práctica:** Inicializar el cliente en `setup()`, no en `process()`.

### 9. Cloud KMS — Claves para tokenización

```bash
gcloud kms keyrings create dlp-keyring --location=europe-west1
gcloud kms keys create dlp-key --keyring=dlp-keyring --location=europe-west1 --purpose=encryption --rotation-period=90d
```

> **Buena práctica:** Rotar claves cada 90 días. Nunca borrar claves — solo desactivar.
> **Problema que evitas:** Datos tokenizados con clave perdida → derecho de acceso imposible.

---

## Resumen: qué técnica para cada dato

| Dato | Técnica | Reversible | Por qué |
|---|---|---|---|
| email | Tokenización FPE | Sí | Derecho de acceso GDPR |
| phone | Masking *** | No | Analytics no usa teléfono |
| name | Tokenización FPE | Sí | Derecho de acceso GDPR |
| address | Generalización (ciudad) | No | Ciudad es suficiente |
| credit_card | Masking ****1234 | No | PCI-DSS lo prohíbe |
| IP | Generalización (/24) | No | Subnet es suficiente |

---

## Dónde se aplica en el pipeline

```
Bronze (PII crudo)  →  Cloud DLP  →  Silver (PII protegido)  →  Gold (sin PII)
   acceso restringido     inspect +      email=TOKEN               solo métricas
                          deidentify     phone=***                 agregadas
                                         address=ciudad
```

---

## Pasos para implementar

| Paso | Qué |
|---|---|
| 1 | `gcloud services enable dlp.googleapis.com cloudkms.googleapis.com` |
| 2 | Crear keyring + clave KMS |
| 3 | Permisos: `roles/dlp.user` + `roles/cloudkms.cryptoKeyEncrypterDecrypter` a sa-functions |
| 4 | Probar con `gcloud dlp inspect-content` y `deidentify-content` |
| 5 | Integrar en Dataflow (DoFn) o Composer (queries MERGE) |
| 6 | Verificar que Silver no tiene PII crudo |
| 7 | Definir en Terraform (`infra/dlp.tf`) |

---

## Costos

| Operación | Precio |
|---|---|
| Inspect | $1/GB |
| Deidentify | $2/GB |
| KMS | $0.06/mes por clave |
| **Estimado E-commerce** | **~$5-10/mes** |
