# Guía de Despliegue en la Nube y Disponibilidad Continua (24/7)

> NO EJECUTAR COMO RECETA VALIDADA. Revisión 15/09/2026: Docker/Compose son borradores sin prueba de construcción. Hay nombres de variables WhatsApp incompatibles con app.py; falta configurar proveedor/modelo, caché de embeddings, persistencia real de SQLite y salud de cada servicio. El volumen `sqlite-requests:/app/human_requests.db` monta un directorio sobre una ruta de archivo. El callback debe exponerse por la entrada restringida 8022, no publicar todo app:app de 8021. El panel necesita un acceso privado diseñado para nube. No se ha desplegado ni demostrado 24/7. Ver `REVISION_AVANCES_20260915.md`.

**Proyecto:** Agente conversacional de Texeira Travel Tour.  
**Compromiso de la tesis:** Servicio en la nube con HTTPS, alta disponibilidad y funcionamiento ininterrumpido 24/7 (Tesis, páginas 15, 61 y 63; Anexo 5, Indicador 3.1).  
**Fecha:** 15 de septiembre de 2026.

---

## 1. Por qué es necesario el despliegue en la nube

Durante las fases iniciales de desarrollo, el software se ejecutó localmente en el PC mediante túneles efímeros (como Cloudflare Quick Tunnel). Conforme a la auditoría del proyecto de investigación (`AUDITORIA_TESIS_20260914.md`):

> *«Un túnel al PC personal no prueba disponibilidad continua 24/7, pues depende de que el portátil permanezca encendido, sin suspensión y con conexión constante de red doméstica.»*

El despliegue en la nube resuelve este requisito dotando al agente de:
1. **Dominio con HTTPS público válido** exigido por Meta for Developers para webhooks de WhatsApp.
2. **Reinicio automático** ante fallos o excepciones inesperadas.
3. **Persistencia de solicitudes** en SQLite (`human_requests.db`) independiente del equipo de desarrollo.
4. **Monitoreo objetivo de disponibilidad (Uptime %)** para sustentar el **Indicador 3.1 del Anexo 5** de la tesis.

---

## 2. Alternativas de Despliegue

### Opción A: PaaS en la Nube (Render / Railway) — *Recomendada por facilidad*
1. Crear una cuenta en [Render](https://render.com) o [Railway](https://railway.app).
2. Crear un nuevo servicio de tipo **Web Service** apuntando al repositorio o subiendo el contenedor.
3. Seleccionar como entorno **Docker** (el sistema detectará automáticamente el [Dockerfile](file:///c:/Users/HP/Desktop/Chat%20bot/texeira-prueba-v4-evidencias/Dockerfile)).
4. Configurar las variables de entorno en el panel (nunca en el código):
   - `GROQ_API_KEY`: Tu clave de API de Groq.
   - `WHATSAPP_VERIFY_TOKEN`: Token acordado con Meta.
   - `WHATSAPP_API_TOKEN`: Token de acceso permanente de Meta.
   - `HF_HUB_OFFLINE`: `1`
   - `TRANSFORMERS_OFFLINE`: `1`
   - `ANONYMIZED_TELEMETRY`: `False`
5. Adjuntar un disco persistente (Persistent Disk) montado en `/app/data` y `/app/logs` para conservar la base de datos de tickets de soporte humano.

### Opción B: Servidor VPS Dedicado (Ubuntu 22.04 / 24.04) — *Control total*
En un servidor VPS (DigitalOcean Droplet, AWS Lightsail o Hetzner):
1. Instalar Docker y Docker Compose:
   ```bash
   sudo apt-get update && sudo apt-get install -y docker.io docker-compose
   ```
2. Clonar el repositorio en el servidor.
3. Crear el archivo `.env` con las credenciales protegidas.
4. Iniciar los servicios orquestados en segundo plano:
   ```bash
   docker-compose up -d --build
   ```
5. Configurar Nginx con Let's Encrypt (Certbot) para apuntar tu subdominio (ej. `bot.texeiratravel.com`) hacia el puerto `8021` con certificado SSL gratuito.

---

## 3. Monitoreo de Disponibilidad 24/7 (Indicador VI 3.1)

Para medir formalmente el porcentaje de disponibilidad requerido por el **Indicador 3.1 del Anexo 5**:
1. Registrar el endpoint de salud `https://<tu-dominio>/chat` en una herramienta de monitoreo externa gratuita (como [UptimeRobot](https://uptimerobot.com) o [Better Uptime](https://betteruptime.com)).
2. Configurar el sondeo HTTP cada **5 minutos**.
3. Al finalizar el periodo de prueba de 15 o 30 días, exportar el reporte de Uptime (%) para incorporarlo como evidencia documental del postest en la tesis.
