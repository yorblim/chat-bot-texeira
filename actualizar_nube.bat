@echo off
chcp 65001 > nul
title Actualizar Bot de WhatsApp en la Nube (Google Cloud Run)
color 0b

echo =====================================================================
echo           ACTUALIZADOR AUTOMÁTICO - TEXEIRA WHATSAPP BOT
echo =====================================================================
echo.
echo Este script subirá tus cambios recientes a Google Cloud Run.
echo (Tu código, prompts, documentos y RAG se compilarán en la nube)
echo.
echo Tus claves y el Token Permanente en Secret Manager NO se tocarán.
echo =====================================================================
echo.

:: Agregar Cloud SDK al PATH por si no está en las variables globales
set "PATH=%PATH%;C:\Users\HP\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin"

:: Verificar que gcloud esté disponible
where gcloud >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    color 0c
    echo [ERROR] No se encontró el comando gcloud de Google Cloud SDK.
    echo Asegúrate de tener instalado Google Cloud SDK.
    echo.
    pause
    exit /b 1
)

echo [1/2] Entrando a la carpeta del proyecto...
cd /d "c:\Users\HP\Desktop\Chat bot\texeira-prueba-v4-evidencias"

echo.
echo [2/2] Subiendo y desplegando en Google Cloud Run (us-central1)...
echo       (Esto puede tomar unos 3-5 minutos mientras compila)
echo.

call gcloud run deploy texeira-whatsapp ^
    --source . ^
    --region us-central1 ^
    --project texeira-whatsapp-bot ^
    --memory 2Gi ^
    --cpu-boost ^
    --min-instances 0 ^
    --max-instances 2 ^
    --platform managed ^
    --allow-unauthenticated ^
    --update-env-vars="ALLOW_CLOUD_RUN=1,ADMIN_USER=admin,APP_BASE_URL=https://texeira-whatsapp-1038134693816.us-central1.run.app" ^
    --remove-env-vars="ADMIN_PASSWORD" ^
    --update-secrets="ADMIN_PASSWORD=ADMIN_PASSWORD:latest"

if %ERRORLEVEL% EQU 0 (
    color 0a
    echo.
    echo =====================================================================
    echo   ¡ACTUALIZACIÓN COMPLETADA CON ÉXITO!
    echo   La nueva versión de tu bot ya está activa y lista para responder.
    echo =====================================================================
) else (
    color 0c
    echo.
    echo =====================================================================
    echo   [ERROR] Hubo un problema al desplegar. Revisa el mensaje arriba.
    echo =====================================================================
)

echo.
pause
