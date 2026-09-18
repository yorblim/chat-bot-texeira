"""Panel local de asesores, sin exponer chat ni endpoints de WhatsApp."""
from fastapi import FastAPI
from app import app as main_app

app=FastAPI(openapi_url=None,docs_url=None,redoc_url=None)
for route in main_app.routes:
    if getattr(route,'path','').startswith('/handoffs'):
        app.router.routes.append(route)
