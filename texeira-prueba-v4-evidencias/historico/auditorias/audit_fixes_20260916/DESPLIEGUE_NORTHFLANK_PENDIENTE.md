# Guía de Despliegue: WhatsApp en Google Cloud Run (GRATIS)

> **REVISIÓN 16/09/2026 — GUÍA NO APROBADA.** Las afirmaciones de gratuidad sin facturación y cold start <2 s son incorrectas/no probadas. No ejecutar los pasos de despliegue: faltan persistencia, filtro .gcloudignore y correcciones del webhook y secretos. Ver `texeira-prueba-v4-evidencias/REVISION_ANTIGRAVITY_20260916.md`. Esta guía conserva contenido histórico contradictorio Northflank/Cloud Run que debe reescribirse antes de usar.

Fecha de actualización: 15/09/2026.
Estado: Dockerfile, .dockerignore y código LISTOS para Cloud Run.
Plataforma elegida: **Google Cloud Run** (Northflank descartado — RAM máxima gratis = 512 MB, insuficiente).

---

## ¿Por qué Cloud Run?

| Criterio | Cloud Run | Northflank Sandbox |
|---|:---:|:---:|
| RAM configurable | **1 GB** | 512 MB máx (gratis) |
| Always-on | Scale-to-zero (ok para webhooks) | ✅ always-on |
| HTTPS incluido | ✅ | ✅ |
| Tarjeta de crédito | Cuenta Google existente basta | No requiere |
| Sin suspensión | ✅ (escala en <2s) | ✅ |
| Precio para bot de prueba | **$0** (dentro del tier gratuito) | Gratis solo hasta 512 MB |

> **Scale-to-zero es perfecto para webhooks**: Meta espera 20 segundos la respuesta.
> Cloud Run arranca en <2s. El primer mensaje tras inactividad tarda 2-3s más — imperceptible.

---

## Archivos listos (corregidos en esta sesión)

| Archivo | Estado |
|---|---|
| `Dockerfile` | ✅ CMD usa `${PORT:-8080}`, descarga embedding en build, EXPOSE 8080 |
| `.dockerignore` | ✅ Excluye .env, DBs, logs, audits, Chroma obsoletos |
| `whatsapp_entry.py` | ✅ Solo expone /webhook y /healthz |
| `runtime_settings.py` | ✅ Prioriza env vars del servidor, fallback .env seguro |

---

## PASO 1 — Instalar Google Cloud SDK (gcloud CLI)

gcloud no está instalado en este PC. Es necesario para el despliegue.

1. Ir a: https://cloud.google.com/sdk/docs/install-sdk
2. Descargar **Google Cloud CLI Installer** para Windows.
3. Ejecutar el instalador (seleccionar "Add gcloud to PATH").
4. Abrir **nueva ventana de PowerShell** y ejecutar:
   ```powershell
   gcloud version
   ```
   Debe mostrar algo como `Google Cloud SDK 460.0.0`.

---

## PASO 2 — Autenticarse y crear el proyecto en GCP

```powershell
# Iniciar sesión con tu cuenta Google
gcloud auth login

# Crear un nuevo proyecto (o usar uno existente)
gcloud projects create texeira-whatsapp-bot --name="Texeira WhatsApp Bot"

# Seleccionar el proyecto activo
gcloud config set project texeira-whatsapp-bot

# Habilitar las APIs necesarias (Cloud Run + Cloud Build + Artifact Registry)
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
```

> Si el proyecto ID `texeira-whatsapp-bot` ya existe, elegir otro nombre único.
> Ver proyectos existentes: `gcloud projects list`

---

## PASO 3 — Desplegar en Cloud Run (sin Docker local)

Cloud Run **no requiere Docker instalado**. El comando `--source .` sube el código
y Google Cloud Build construye la imagen usando el Dockerfile automáticamente.

```powershell
# Desde la carpeta del proyecto
cd "c:\Users\HP\Desktop\Chat bot\texeira-prueba-v4-evidencias"

# Desplegar (primera vez; tarda ~5-10 min por descarga del modelo embeddings)
gcloud run deploy texeira-whatsapp `
  --source . `
  --region us-central1 `
  --platform managed `
  --allow-unauthenticated `
  --memory 1Gi `
  --cpu 1 `
  --min-instances 0 `
  --max-instances 1 `
  --port 8080 `
  --set-env-vars "TEXEIRA_ENABLE_WHATSAPP=true,TEXEIRA_ENABLE_MESSENGER=false,TEXEIRA_ENABLE_ADVISOR_NOTIFICATIONS=false,TEXEIRA_STATE_DIR=/app/state,WHATSAPP_TEST_MODE=true,LLM_PROVIDER=groq,LLM_MODEL=qwen/qwen3.8-27b,HF_HUB_OFFLINE=1,TRANSFORMERS_OFFLINE=1,ANONYMIZED_TELEMETRY=False" `
  --set-secrets "META_VERIFY_TOKEN=META_VERIFY_TOKEN:latest,META_ACCESS_TOKEN=META_ACCESS_TOKEN:latest,META_PHONE_NUMBER_ID=META_PHONE_NUMBER_ID:latest,META_APP_SECRET=META_APP_SECRET:latest,GROQ_API_KEY=GROQ_API_KEY:latest"
```

> **IMPORTANTE**: Las credenciales Meta y Groq se configuran como Secrets de GCP (Paso 4),
> NO se pasan en texto plano. El comando anterior asume que los Secrets ya existen.

---

## PASO 4 — Configurar Secrets (credenciales Meta + Groq)

**Antes del primer despliegue**, crear los secrets en GCP Secret Manager:

```powershell
# Habilitar Secret Manager
gcloud services enable secretmanager.googleapis.com

# Crear cada secret (te pedirá el valor; escríbelo sin mostrarlo)
echo "TU_META_VERIFY_TOKEN" | gcloud secrets create META_VERIFY_TOKEN --data-file=-
echo "TU_META_ACCESS_TOKEN" | gcloud secrets create META_ACCESS_TOKEN --data-file=-
echo "TU_META_PHONE_NUMBER_ID" | gcloud secrets create META_PHONE_NUMBER_ID --data-file=-
echo "TU_META_APP_SECRET" | gcloud secrets create META_APP_SECRET --data-file=-
echo "TU_GROQ_API_KEY" | gcloud secrets create GROQ_API_KEY --data-file=-
```

> **ALTERNATIVA más segura**: usar la consola web de GCP → Secret Manager → Create Secret,
> y escribir el valor directamente en el campo del formulario (nunca en el historial del terminal).

Dar permisos al servicio de Cloud Run para leer los secrets:
```powershell
# Obtener el email del service account de Cloud Run
$PROJECT_ID = "texeira-whatsapp-bot"
$SA = "$PROJECT_ID-compute@developer.gserviceaccount.com"

# Dar acceso a cada secret
gcloud secrets add-iam-policy-binding META_VERIFY_TOKEN --member="serviceAccount:$SA" --role="roles/secretmanager.secretAccessor"
gcloud secrets add-iam-policy-binding META_ACCESS_TOKEN --member="serviceAccount:$SA" --role="roles/secretmanager.secretAccessor"
gcloud secrets add-iam-policy-binding META_PHONE_NUMBER_ID --member="serviceAccount:$SA" --role="roles/secretmanager.secretAccessor"
gcloud secrets add-iam-policy-binding META_APP_SECRET --member="serviceAccount:$SA" --role="roles/secretmanager.secretAccessor"
gcloud secrets add-iam-policy-binding GROQ_API_KEY --member="serviceAccount:$SA" --role="roles/secretmanager.secretAccessor"
```

---

## PASO 5 — Verificar /healthz

Una vez desplegado, Cloud Run muestra la URL del servicio:
```
Service URL: https://texeira-whatsapp-XXXXXXXX-uc.a.run.app
```

Abrir en navegador:
```
https://texeira-whatsapp-XXXXXXXX-uc.a.run.app/healthz
```
Respuesta esperada: `{"status":"ok"}`

---

## PASO 6 — Conectar callback en Meta for Developers

1. Ir a https://developers.facebook.com → tu aplicación → WhatsApp → Configuration.
2. **Callback URL**: `https://texeira-whatsapp-XXXXXXXX-uc.a.run.app/webhook`
3. **Verify token**: el valor de `META_VERIFY_TOKEN` configurado.
4. Clic en **Verify and save**.
5. Suscribir al evento `messages`.

---

## PASO 7 — Probar con los tres números de prueba

1. Enviar mensaje desde cada número de prueba.
2. Confirmar respuesta del bot.
3. **Apagar el PC** → enviar otro mensaje.
4. Confirmar respuesta sin el PC.

---

## Limitaciones

- **Disco efímero**: SQLite se reinicia en cada cold start. Los registros históricos quedan en el PC.
  Para persistencia usar Cloud SQL (PostgreSQL gratuito primeros 30 días, luego ~$8/mes) — opcional para el prototipo.
- **Cold start**: primer mensaje tras inactividad tarda 2-3s adicionales (imperceptible para WhatsApp).
- **Token Meta con expiración**: verificar vigencia del token antes de probar.

---

## Advertencias

- NO incluir credenciales en el repositorio Git ni en el historial del terminal.
- NO seleccionar `min-instances=1` sin querer pagar (ese parámetro mantiene siempre un contenedor activo).
- NO enviar mensajes a terceros sin autorización explícita.
- Confirmar prueba con PC apagado antes de declarar disponibilidad 24/7.


Fecha de actualización: 15/09/2026.
Estado: Dockerfile, docker-compose.yml y .dockerignore CORREGIDOS en esta sesión.
Repositorio privado disponible. Listo para conectar a Northflank.

---

## Objetivo

Desplegar únicamente el webhook de WhatsApp en Northflank Sandbox gratuito.
- Puerto expuesto: **8022** (webhook + /healthz).
- Paneles, chat y asesores quedan locales (no se exponen en producción).
- Messenger aplazado (sin acceso a Facebook).

---

## Recursos de Northflank Developer Sandbox (Gratuitos)

| Recurso | Disponible |
|---|---|
| RAM | 256 MB (nf-compute-10) o 512 MB (nf-compute-20) |
| CPU | 0.1 vCPU compartida |
| Disco | Efímero (se reinicia al re-deploy) |
| Builds | Incluidos |
| Suspensión | Sin suspensión (diferencia con Render) |
| Dominio HTTPS | Incluido (`*.northflank.app`) |

> **LIMITACIÓN DOCUMENTADA**: El disco efímero significa que los SQLite
> (`trial_logs.db`, `human_requests.db`) se reinician en cada re-deploy.
> Los registros históricos se conservan en el PC. Esta limitación es aceptable
> para el prototipo de tesis. Se puede mitigar con un Addon de PostgreSQL gratuito
> de Northflank en una fase posterior.

---

## Archivos Corregidos en Esta Sesión

| Archivo | Cambios |
|---|---|
| `Dockerfile` | CMD→whatsapp_entry:8022, HEALTHCHECK→/healthz:8022, descarga modelo embedding durante build |
| `docker-compose.yml` | Variables META_* correctas, servicio único WhatsApp, TEXEIRA_STATE_DIR |
| `.dockerignore` | NUEVO — excluye .env, DBs, logs, audits, Chroma obsoletos, scripts de test |

---

## Pasos en la UI de Northflank

### PASO 1 — Conectar el repositorio privado

Ya estás en la pantalla "Create new → Service". Completa así:

**Basic information:**
- Service name: `texeira-whatsapp`

**Source:**
- Seleccionar: **Combined** (Build and deploy a Git repo)
- Repository: seleccionar tu repo privado (conectar GitHub si no lo has hecho)
- Branch: `main` (o la rama con el código actualizado)

**Build options:**
- Build type: **Dockerfile**
- Build context: `/` (directorio raíz)
- Dockerfile location: `/Dockerfile`
- BuildKit: **enabled** (sugerido)

### PASO 2 — Recursos

- Compute plan: **nf-compute-10** (0.1 vCPU, 256 MB RAM) — probar primero.
- Si el build falla por OOM durante carga del modelo embedding → cambiar a **nf-compute-20** (512 MB), que también es gratuito en Sandbox.
- Instances: **1**

### PASO 3 — Networking (Puerto)

- Clic en **Add port**
- Port name: `webhook`
- Port number: `8022`
- Protocol: `HTTP`
- Marcar como **Public** para obtener URL HTTPS

### PASO 4 — Secret Group (Credenciales — NO escribir aquí directamente)

**Antes de crear el servicio**, crear un Secret Group:
1. En el proyecto `texeira-bot` → **Secret group** → Create secret group.
2. Nombre del grupo: `texeira-meta-secrets`
3. Añadir estas variables (una por una, tipo "Secret"):

| Variable | Valor (introducir en Northflank, no aquí) |
|---|---|
| `TEXEIRA_ENABLE_WHATSAPP` | `true` |
| `TEXEIRA_ENABLE_MESSENGER` | `false` |
| `TEXEIRA_ENABLE_ADVISOR_NOTIFICATIONS` | `false` |
| `META_VERIFY_TOKEN` | *tu token de verificación elegido* |
| `META_ACCESS_TOKEN` | *token de acceso del número de prueba* |
| `META_PHONE_NUMBER_ID` | *ID del número de teléfono de Meta* |
| `META_APP_SECRET` | *App Secret de la aplicación Meta* |
| `WHATSAPP_TEST_MODE` | `true` |
| `WHATSAPP_TEST_BSUID_MAP` | (opcional; dejar vacío si no usas BSUIDs) |
| `LLM_PROVIDER` | `groq` |
| `LLM_MODEL` | `qwen/qwen3.8-27b` |
| `GROQ_API_KEY` | *tu clave de Groq* |
| `TEXEIRA_STATE_DIR` | `/app/state` |

4. En el servicio `texeira-whatsapp` → Environment → **Add secret group** → seleccionar `texeira-meta-secrets`.

### PASO 5 — Crear el servicio

- Clic en **Create service**.
- Northflank iniciará el build (puede tardar 5–10 minutos la primera vez por la descarga del modelo de embeddings).
- Verificar en el tab **Build** que no haya errores.

### PASO 6 — Verificar /healthz

Una vez desplegado, copiar la URL HTTPS asignada (ej. `https://texeira-whatsapp-xxxxx.northflank.app`).
Abrir en navegador: `https://texeira-whatsapp-xxxxx.northflank.app/healthz`
Debe responder: `{"status": "ok"}`

### PASO 7 — Conectar callback en Meta for Developers

1. Ir a https://developers.facebook.com → tu aplicación → WhatsApp → Configuration.
2. **Callback URL**: `https://texeira-whatsapp-xxxxx.northflank.app/webhook`
3. **Verify token**: el mismo valor de `META_VERIFY_TOKEN` configurado en Northflank.
4. Clic en **Verify and save**.
5. Suscribir al evento `messages`.

### PASO 8 — Probar con los tres números de prueba

1. Enviar un mensaje de WhatsApp desde cada número de prueba.
2. Confirmar que el bot responde.
3. **Apagar el PC** y enviar otro mensaje desde el teléfono.
4. Confirmar que responde sin depender del PC.

---

## Advertencias

- NO incluir credenciales en el repositorio Git.
- NO seleccionar plan de pago (Pay as you go) sin autorización.
- NO exponer los paneles /dashboard o /handoffs públicamente.
- El token de acceso de Meta tiene expiración; revisar vigencia antes de la prueba.
- Confirmar prueba con PC apagado antes de declarar disponibilidad 24/7.

---

## Cierre Esperado

- URL HTTPS estable con /healthz respondiendo.
- Webhook Meta verificado y suscrito a `messages`.
- Bot responde a los tres números de prueba sin el PC encendido.
- Limitación de disco efímero documentada.


## Objetivo y decisiones del usuario

- Que tres números de prueba ya registrados en Meta conversen con el bot sin depender del PC encendido.
- Mantener el número de prueba +1 555 205 3249; no migrar ahora a número comercial ni modificar destinatarios existentes.
- Presupuesto gratuito. Messenger queda pendiente porque el usuario no tiene acceso a la página de Facebook.
- Usuario pidió alternativa a Oracle con tarjeta. Northflank Sandbox es candidato; no se ha confirmado que su cuota sirva para este proceso.

## Pantalla actual conocida

URL https://app.northflank.com/signup. Capturas muestran equipo «Jorcaef's Team», Developer Sandbox (Free), Pay as you go y botón Continue. Se indicó **Developer Sandbox — Free**, invitaciones vacías y Continue. Aún no se confirmó finalización del registro, creación del equipo ni proyecto. No seleccionar Pay as you go: el presupuesto no autoriza cobros.

## Preparación realizada

Carpeta activa: `C:\Users\HP\Desktop\Chat bot\texeira-prueba-v4-evidencias`.

- `runtime_settings.py`: variables del servidor tienen prioridad; fallback al .env del original para uso local. Las credenciales Meta solo se habilitan con la opción del canal. Rechaza configuración WhatsApp incompleta.
- `TEXEIRA_STATE_DIR`: directorio configurable para `trial_logs.db` y `human_requests.db`. Métricas y solicitudes apuntan a almacenamiento configurable. Debe montarse almacenamiento persistente real, no asumir que el disco del contenedor lo es.
- `whatsapp_entry.py`: expone webhook y `/healthz`; mantiene fuera chat, paneles y registros. El estado HTTP no prueba disponibilidad de Groq ni credenciales Meta.
- Docker copia el nuevo módulo, pero Docker/Compose siguen siendo borradores con fallos previos. No hay Docker instalado detectable en este PC. No se construyó imagen.
- Pruebas después de estos cambios: `test_runtime_settings.py`, `test_operational_metrics.py`, `test_handoff.py`, `test_audit_20260912.py` terminaron con exit=0. Logs y respaldos: `audit_deploy_20260915/`. Pruebas locales, sin APIs externas.
- Estos últimos cambios de portabilidad no se cargaron mediante otro reinicio local. PID 21376 era el chat tras la revisión anterior; no asumir vigente.

## Validaciones necesarias antes de desplegar

1. Verificar desde la cuenta los límites gratuitos de RAM, CPU, disco persistente, builds y tráfico. El proceso Windows observado consumía aproximadamente 771 MB de working set; no es medición Linux ni máximo bajo carga. No prometer que entrará en un plan pequeño.
2. Si los recursos gratuitos no alcanzan, informar con evidencia antes de rediseñar RAG, quitar características, cambiar proveedor de datos o contratar algo.
3. Preparar contexto Docker mínimo: módulos activos, catálogo/evidencias e índice vigente. Excluir .env, logs, bases del piloto, copias, documentos de evaluación y respaldos. El índice activo es `chroma_f1_confirmado_20260915_db` (20 documentos verificados).
4. Resolver instalación/caché del modelo `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`: el contenedor actual declara modo offline sin copiar/descargar caché. Probar construcción y arranque en la plataforma.
5. Ajustar inicio a `whatsapp_entry:app`, host 0.0.0.0 y puerto aceptado por plataforma; salud `/healthz`. No publicar `app:app` con todos los paneles.
6. Configurar secretos en el gestor de la plataforma, no en Git ni logs: `LLM_PROVIDER`, `LLM_MODEL`, `GROQ_API_KEY`, y `META_VERIFY_TOKEN`, `META_ACCESS_TOKEN`, `META_PHONE_NUMBER_ID`, `META_APP_SECRET`. Revisar `WHATSAPP_TEST_MODE` y mapa de destinatarios si la configuración actual los usa. No imprimir valores. Habilitar `TEXEIRA_ENABLE_WHATSAPP=true`; Messenger y avisos al asesor permanecen deshabilitados.
7. Las variables WHATSAPP_API_TOKEN/WHATSAPP_VERIFY_TOKEN del Compose antiguo no coinciden con el código. El volumen sobre `/app/human_requests.db` monta un directorio donde debe existir un archivo: corregir antes de usar. Definir persistencia de ambas bases y respaldo/reversión para actualizaciones.
8. No asumir token permanente: verificar vigencia de Meta y definir renovación antes de prometer autonomía. Los registros históricos tuvieron expiración de tokens.
9. Revisar autorización de subida de código/datos y configuración concreta antes de ejecución; no interpretar registro gratuito como autorización de gasto o de repositorio público. No eludir bloqueos automáticos.
10. Tras servidor estable, cambiar callback de Meta, verificar suscripción messages y probar con destinatarios existentes. No enviar mensajes nuevos a terceros sin autorización explícita. Confirmar una prueba iniciada por el usuario con PC apagado y persistencia tras reinicio/despliegue.

## Investigación consultada (revalidar si cambia)

- Northflank anuncia Sandbox sin suspensión: https://northflank.com/pricing
- Publicación oficial indica sin tarjeta: https://northflank.com/blog/how-to-deploy-vibe-coded-v0-apps-to-production
- Render Free suspende tras inactividad y no conserva archivos: https://render.com/docs/free
- No se verificaron cuotas efectivas de la cuenta Northflank ni compatibilidad del bot. No existe aún URL remota del bot.

## Cierre esperado

URL HTTPS remota verificada, webhook Meta conectado, bot responde a los destinatarios de prueba con PC apagado, datos conservados tras reinicio, procedimiento de actualización y recuperación documentado. Distinguir esto de disponibilidad garantizada 24/7 o evaluación académica completa.
