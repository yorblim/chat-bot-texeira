"""Entrada pública limitada al webhook (Cloud Run / producción).

Estrategia de arranque:
  1. El startup event carga el RAG de forma síncrona (bloqueante) vía executor.
     Cloud Run con --cpu-boost mantiene CPU completa durante el arranque.
  2. Una vez cargado, el tráfico POST /webhook se redirige al ASGI app
     completo de app.py usando el Request object de Starlette — FastAPI
     gestiona la inyección de dependencias (BackgroundTasks, etc.).
  3. /healthz responde con estado de carga.
  4. /webhook GET resuelve el handshake de Meta directamente (sin RAG).
"""
import asyncio
import os
import logging

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.testclient import TestClient  # noqa — solo para typing hint

logger = logging.getLogger("whatsapp_entry")

# ------------------------------------------------------------------ #
# App pública — solo expone /webhook y /healthz                       #
# ------------------------------------------------------------------ #
app = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)

_state: dict = {"ready": False, "local_app": None, "error": None}


# ------------------------------------------------------------------ #
# Carga del RAG en el startup (bloqueante vía executor)               #
# ------------------------------------------------------------------ #
@app.on_event("startup")
async def startup() -> None:
    """Carga el RAG de forma bloqueante — Cloud Run espera a que termine."""
    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(None, _sync_load)
        _state["ready"] = True
        logger.info("[ENTRY] RAG cargado correctamente.")
    except Exception as exc:
        _state["error"] = str(exc)
        logger.error(f"[ENTRY] Error al cargar el RAG: {exc}")


def _sync_load() -> None:
    """Import síncrono pesado ejecutado en thread pool."""
    try:
        import runtime_settings  # noqa: PLC0415
        runtime_settings.configure()
    except Exception as e:
        logger.warning(f"[ENTRY] runtime_settings.configure() falló: {e}")

    from app import app as _local  # noqa: PLC0415
    _state["local_app"] = _local

    import asyncio as _aio  # noqa: PLC0415
    _loop = _aio.new_event_loop()
    try:
        for handler in _local.router.on_startup:
            if _aio.iscoroutinefunction(handler):
                _loop.run_until_complete(handler())
            else:
                handler()
    finally:
        _loop.close()


# ------------------------------------------------------------------ #
# Endpoints                                                           #
# ------------------------------------------------------------------ #
@app.get("/healthz")
def health() -> dict:
    if _state.get("error"):
        return {"status": "error", "detail": _state["error"]}
    return {"status": "ok" if _state["ready"] else "warming_up"}


@app.get("/webhook")
async def meta_verify(request: Request) -> Response:
    """Handshake de verificación Meta — no requiere RAG."""
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    expected = os.environ.get("META_VERIFY_TOKEN", "")
    if mode == "subscribe" and token == expected and challenge:
        return Response(content=challenge, media_type="text/plain")
    return Response(status_code=403)


@app.post("/webhook")
async def meta_webhook(request: Request) -> Response:
    """Mensajes WhatsApp/Messenger entrantes — delega al ASGI app completo."""
    if not _state["ready"] or _state["local_app"] is None:
        logger.warning("[ENTRY] POST /webhook antes de que el RAG esté listo.")
        return Response(status_code=202)

    local_app = _state["local_app"]

    # Construir scope ASGI a partir del request actual
    scope = request.scope.copy()
    # Asegurar que el path sea /webhook y el método POST
    scope["path"] = "/webhook"
    scope["method"] = "POST"

    # Buffer del body ya leído
    body_bytes = await request.body()

    async def receive():
        return {"type": "http.request", "body": body_bytes, "more_body": False}

    response_started = {}
    response_body = bytearray()

    async def send(message):
        if message["type"] == "http.response.start":
            response_started["status"] = message["status"]
            response_started["headers"] = message.get("headers", [])
        elif message["type"] == "http.response.body":
            response_body.extend(message.get("body", b""))

    try:
        await local_app(scope, receive, send)
    except Exception as exc:
        logger.error(f"[ENTRY] Error en app local ASGI: {exc}")
        return JSONResponse({"error": str(exc)}, status_code=500)

    status_code = response_started.get("status", 200)
    headers = dict(response_started.get("headers", []))
    return Response(
        content=bytes(response_body),
        status_code=status_code,
        headers={k.decode() if isinstance(k, bytes) else k: v.decode() if isinstance(v, bytes) else v
                 for k, v in (response_started.get("headers", []))},
    )
