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
from auth_middleware import _check_credentials, panel_csrf_token

def install(app):
    """Instala las rutas del catálogo dinámico y endpoints multimedia en FastAPI."""
    # Cloud Run puede reiniciar o alternar instancias mientras el panel sigue
    # abierto. Derivar el token del secreto compartido evita tokens por proceso.
    # El dominio separa este valor del password y de otros paneles.
    csrf_token = panel_csrf_token('catalog')
    app.state.catalog_csrf_token = csrf_token

    # Inicializar base de datos y sembrar catálogo canónico en startup
    catalog_service.init_catalog_db()

    def _validate_csrf(request: Request) -> bool:
        """Verifica que el header X-Catalog-CSRF coincida de forma segura con el token activo."""
        client_csrf = request.headers.get("X-Catalog-CSRF", "")
        if not client_csrf:
            return False
        return hmac.compare_digest(client_csrf.encode("utf-8"), csrf_token.encode("utf-8"))

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
        if not _check_credentials(request):
            return Response(status_code=401)
        return HTMLResponse(get_catalog_html(csrf_token), headers={"Cache-Control": "no-store"})

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
        return JSONResponse({"ok": True, "csrf_token": csrf_token}, headers={"Cache-Control": "no-store"})

    def _normalize_hhmm(raw_val: str, default_val: str) -> str:
        val = str(raw_val or "").strip()
        parts = val.split(":")
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            hh, mm = int(parts[0]), int(parts[1])
            if 0 <= hh <= 23 and 0 <= mm <= 59:
                return f"{hh:02d}:{mm:02d}"
        return default_val

    def _as_bool(raw_val, default_val: bool) -> bool:
        if raw_val is None:
            return default_val
        if isinstance(raw_val, bool):
            return raw_val
        return str(raw_val).strip().lower() in ("true", "1", "yes", "on")

    @app.get("/api/catalog/settings")
    async def get_catalog_settings(request: Request):
        if not _check_credentials(request):
            return JSONResponse({"ok": False, "error": "No autorizado"}, status_code=401)
        settings = catalog_service.get_all_agency_settings()
        advisor_phone = settings.get("advisor_whatsapp_phone") or os.getenv("ADVISOR_WHATSAPP_PHONE") or os.getenv("ADVISOR_PHONE") or "51953767860"
        notifications_enabled = settings.get("advisor_notifications_enabled")
        if notifications_enabled is None:
            notifications_enabled = os.getenv("TEXEIRA_ENABLE_ADVISOR_NOTIFICATIONS", "false").lower() in ("true", "1", "yes")
        else:
            notifications_enabled = str(notifications_enabled).lower() in ("true", "1", "yes")

        hours_enabled = _as_bool(
            settings.get("advisor_hours_enabled"),
            _as_bool(os.getenv("TEXEIRA_ENABLE_ADVISOR_HOURS"), True),
        )
        hours_start = _normalize_hhmm(
            settings.get("advisor_hours_start") or os.getenv("ADVISOR_HOURS_START"),
            "09:00",
        )
        hours_end = _normalize_hhmm(
            settings.get("advisor_hours_end") or os.getenv("ADVISOR_HOURS_END"),
            "18:00",
        )
        workdays = settings.get("advisor_workdays") or os.getenv("ADVISOR_WORKDAYS") or "mon_sat"
        if workdays not in ("mon_sat", "everyday"):
            workdays = "mon_sat"
        quiet_after_hours = _as_bool(
            settings.get("advisor_quiet_after_hours"),
            _as_bool(os.getenv("TEXEIRA_ADVISOR_QUIET_AFTER_HOURS"), True),
        )

        return JSONResponse({
            "ok": True,
            "advisor_whatsapp_phone": advisor_phone,
            "advisor_notifications_enabled": notifications_enabled,
            "advisor_hours_enabled": hours_enabled,
            "advisor_hours_start": hours_start,
            "advisor_hours_end": hours_end,
            "advisor_workdays": workdays,
            "advisor_quiet_after_hours": quiet_after_hours,
        })

    @app.post("/api/catalog/settings")
    async def save_catalog_settings(request: Request):
        ok_auth, status, err = _authorized_mutation(request)
        if not ok_auth:
            return JSONResponse({"ok": False, "error": err}, status_code=status)
        try:
            data = await request.json()
            if "advisor_whatsapp_phone" in data:
                raw_phone = str(data["advisor_whatsapp_phone"]).strip()
                catalog_service.set_agency_setting("advisor_whatsapp_phone", raw_phone)
            if "advisor_notifications_enabled" in data:
                val = "true" if _as_bool(data["advisor_notifications_enabled"], False) else "false"
                catalog_service.set_agency_setting("advisor_notifications_enabled", val)
            if "advisor_hours_enabled" in data:
                val = "true" if _as_bool(data["advisor_hours_enabled"], True) else "false"
                catalog_service.set_agency_setting("advisor_hours_enabled", val)
            if "advisor_hours_start" in data:
                raw_s = str(data["advisor_hours_start"]).strip()
                norm_s = _normalize_hhmm(raw_s, "")
                if not norm_s:
                    return JSONResponse({"ok": False, "error": "Hora de inicio inválida (usa HH:MM)"}, status_code=400)
                catalog_service.set_agency_setting("advisor_hours_start", norm_s)
            if "advisor_hours_end" in data:
                raw_e = str(data["advisor_hours_end"]).strip()
                norm_e = _normalize_hhmm(raw_e, "")
                if not norm_e:
                    return JSONResponse({"ok": False, "error": "Hora de cierre inválida (usa HH:MM)"}, status_code=400)
                catalog_service.set_agency_setting("advisor_hours_end", norm_e)
            if "advisor_workdays" in data:
                wd = str(data["advisor_workdays"]).strip()
                if wd not in ("mon_sat", "everyday"):
                    return JSONResponse({"ok": False, "error": "Días laborales inválidos"}, status_code=400)
                catalog_service.set_agency_setting("advisor_workdays", wd)
            if "advisor_quiet_after_hours" in data:
                val = "true" if _as_bool(data["advisor_quiet_after_hours"], True) else "false"
                catalog_service.set_agency_setting("advisor_quiet_after_hours", val)
            return JSONResponse({"ok": True, "message": "Ajustes guardados correctamente"})
        except Exception as e:
            return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

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

    # --- ENDPOINTS DE TARIFAS ESPECIALES (Tour hasMany Rates) ---

    @app.get("/api/catalog/tours/{entity_id}/rates")
    async def list_tour_rates(entity_id: str, request: Request):
        all_rates = request.query_params.get("all", "1").lower() in ("1", "true", "yes")
        active_only = not all_rates
        rates = catalog_service.get_tour_rates(entity_id, active_only=active_only)
        return JSONResponse(rates)

    @app.post("/api/catalog/tours/{entity_id}/rates")
    async def save_tour_rate(entity_id: str, request: Request):
        ok_auth, status, err = _authorized_mutation(request)
        if not ok_auth:
            return JSONResponse({"ok": False, "error": err}, status_code=status)
        try:
            data = await request.json()
            data["entity_id"] = entity_id
            ok, res = catalog_service.upsert_tour_rate(data)
            if not ok:
                return JSONResponse({"ok": False, "error": res}, status_code=400)
            return JSONResponse({"ok": True, "rate_id": res})
        except Exception as e:
            return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

    @app.delete("/api/catalog/rates/{rate_id}")
    async def remove_tour_rate(rate_id: int, request: Request):
        ok_auth, status, err = _authorized_mutation(request)
        if not ok_auth:
            return JSONResponse({"ok": False, "error": err}, status_code=status)
        ok, msg = catalog_service.delete_tour_rate(rate_id)
        if not ok:
            return JSONResponse({"ok": False, "error": msg}, status_code=400)
        return JSONResponse({"ok": True, "message": msg})

    # --- ENDPOINTS DE BLOQUEO DE FECHAS Y CUPOS (Tour hasMany Blocked Dates) ---

    @app.get("/api/catalog/tours/{entity_id}/dates")
    async def list_tour_dates(entity_id: str, request: Request):
        future_only = request.query_params.get("future_only", "1").lower() in ("1", "true", "yes")
        dates = catalog_service.get_tour_blocked_dates(entity_id, future_only=future_only)
        return JSONResponse(dates)

    @app.post("/api/catalog/tours/{entity_id}/dates")
    async def save_tour_date(entity_id: str, request: Request):
        ok_auth, status, err = _authorized_mutation(request)
        if not ok_auth:
            return JSONResponse({"ok": False, "error": err}, status_code=status)
        try:
            data = await request.json()
            data["entity_id"] = entity_id
            ok, res = catalog_service.upsert_tour_blocked_date(data)
            if not ok:
                return JSONResponse({"ok": False, "error": res}, status_code=400)
            return JSONResponse({"ok": True, "date_id": res})
        except Exception as e:
            return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

    @app.delete("/api/catalog/tours/{entity_id}/dates/{tour_date}")
    async def remove_tour_date(entity_id: str, tour_date: str, request: Request):
        ok_auth, status, err = _authorized_mutation(request)
        if not ok_auth:
            return JSONResponse({"ok": False, "error": err}, status_code=status)
        ok, msg = catalog_service.delete_tour_blocked_date(tour_date, entity_id=entity_id)
        if not ok:
            return JSONResponse({"ok": False, "error": msg}, status_code=400)
        return JSONResponse({"ok": True, "message": msg})

    @app.delete("/api/catalog/dates/{date_id}")
    async def remove_tour_date_by_id(date_id: int, request: Request):
        ok_auth, status, err = _authorized_mutation(request)
        if not ok_auth:
            return JSONResponse({"ok": False, "error": err}, status_code=status)
        ok, msg = catalog_service.delete_tour_blocked_date(date_id)
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
