"""Entrada pública limitada al webhook; el panel y los registros quedan locales."""
from fastapi import FastAPI
from app import app as local_app

app = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)
for route in local_app.routes:
    if getattr(route, 'path', None) == '/webhook':
        app.router.routes.append(route)
app.router.on_startup.extend(local_app.router.on_startup)
app.router.on_shutdown.extend(local_app.router.on_shutdown)
