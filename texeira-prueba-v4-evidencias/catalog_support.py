"""
catalog_support.py — Módulo de endpoints y soporte para el Catálogo Dinámico de Texeira Travel.

Registra las rutas de administración de tours, precios oficiales y subida
de fotos/folletos protegidas por CSRF y Basic Auth.
"""

import os
import secrets
from fastapi import Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse, Response, FileResponse

import catalog_service
from catalog_ui import get_catalog_html

IMAGES_DIR = catalog_service.IMAGES_DIR
BROCHURES_DIR = catalog_service.BROCHURES_DIR


import hmac
from auth_middleware import _check_credentials

def install(app):
    """Instala las rutas del catálogo dinámico y endpoints multimedia en FastAPI."""
    csrf_token = secrets.token_urlsafe(24)
    app.state.catalog_csrf_token = csrf_token

    # Inicializar base de datos y sembrar catálogo canónico en startup
    catalog_service.init_catalog_db()

    def _validate_csrf(request: Request) -> bool:
        """Verifica que el header X-Catalog-CSRF coincida de forma segura con el token activo."""
        client_csrf = request.headers.get("X-Catalog-CSRF", "")
        if not client_csrf:
            return False
        return hmac.compare_digest(client_csrf, csrf_token)

    def _authorized_mutation(request: Request) -> tuple:
        """
        Exige autenticación y token CSRF válido en todas las mutaciones del catálogo.
        Basic Auth y una dirección local NO deben saltarse esta validación.
        Retorna (autorizado: bool, status_code: int, mensaje_error: str).
        """
        if not _check_credentials(request):
            return False, 401, "No autenticado. Credenciales inválidas o ausentes."
        if not _validate_csrf(request):
            return False, 403, "Token CSRF inválido o faltante."
        return True, 200, ""

    @app.get("/catalogo", response_class=HTMLResponse)
    async def catalog_page(request: Request):
        return HTMLResponse(get_catalog_html(csrf_token))

    @app.get("/api/catalog/tours")
    async def list_catalog_tours(request: Request):
        all_param = request.query_params.get("all", "0").lower() in ("1", "true", "yes")
        active_param = request.query_params.get("active_only", "1" if not all_param else "0").lower()
        active_only = active_param not in ("false", "0", "no") and not all_param
        tours = catalog_service.get_all_tours(active_only=active_only)
        return JSONResponse(tours)

    @app.get("/api/catalog/tours/{entity_id}")
    async def get_catalog_tour(entity_id: str):
        tour = catalog_service.get_tour_by_id(entity_id)
        if not tour:
            return JSONResponse({"error": "Tour no encontrado"}, status_code=404)
        return JSONResponse(tour)

    @app.get("/api/catalog/csrf-token")
    async def get_catalog_csrf_token(request: Request):
        if not _check_credentials(request):
            return JSONResponse({"ok": False, "error": "No autorizado"}, status_code=401)
        return JSONResponse({"ok": True, "csrf_token": csrf_token})

    @app.post("/api/catalog/tours")
    async def create_or_update_tour(request: Request):
        ok_auth, status, err = _authorized_mutation(request)
        if not ok_auth:
            return JSONResponse({"ok": False, "error": err}, status_code=status)
        try:
            data = await request.json()
            ok, msg = catalog_service.upsert_tour(data)
            if not ok:
                return JSONResponse({"ok": False, "error": msg}, status_code=400)
            return JSONResponse({"ok": True, "entity_id": msg})
        except Exception as e:
            return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

    @app.post("/api/catalog/upload/{entity_id}")
    async def upload_tour_asset(
        entity_id: str,
        request: Request,
        file: UploadFile = File(...),
        asset_type: str = Form("photo")
    ):
        ok_auth, status, err = _authorized_mutation(request)
        if not ok_auth:
            return JSONResponse({"ok": False, "error": err}, status_code=status)
        try:
            content = await file.read()
            if len(content) > 15 * 1024 * 1024:
                return JSONResponse({"error": "El archivo excede el tamaño máximo permitido (15MB)"}, status_code=400)

            ok, filename_or_err = catalog_service.save_asset(
                entity_id=entity_id,
                asset_type=asset_type,
                filename=file.filename or f"asset_{entity_id}",
                content_bytes=content,
            )
            if not ok:
                return JSONResponse({"ok": False, "error": filename_or_err}, status_code=400)
            return JSONResponse({"ok": True, "filename": filename_or_err})
        except Exception as e:
            return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

    @app.delete("/api/catalog/tours/{entity_id}")
    async def remove_tour(entity_id: str, request: Request):
        ok_auth, status, err = _authorized_mutation(request)
        if not ok_auth:
            return JSONResponse({"ok": False, "error": err}, status_code=status)
        ok, msg = catalog_service.delete_tour(entity_id)
        if not ok:
            return JSONResponse({"ok": False, "error": msg}, status_code=400)
        return JSONResponse({"ok": True, "message": msg})

    @app.get("/brochures/{filename}")
    async def serve_brochure(filename: str):
        import re as _re
        if not _re.match(r"^[\w\-\.]+\.pdf$", filename, _re.IGNORECASE):
            return JSONResponse({"error": "Nombre de archivo no válido"}, status_code=400)

        file_path = BROCHURES_DIR / filename
        if file_path.exists():
            return FileResponse(str(file_path), media_type="application/pdf")

        asset = catalog_service.get_asset_bytes(filename, "brochure")
        if asset:
            content_bytes, media_type = asset
            return Response(content=content_bytes, media_type=media_type)

        return JSONResponse({"error": "Folleto no encontrado"}, status_code=404)
