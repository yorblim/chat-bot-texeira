"""Panel local de asesores, sin exponer chat ni endpoints de WhatsApp."""
from fastapi import FastAPI
from app import app as main_app

app=FastAPI(openapi_url=None,docs_url=None,redoc_url=None)
from auth_middleware import install_auth
install_auth(app)
for route in main_app.routes:
    if getattr(route,'path','').startswith(('/handoffs','/operational-metrics')):
        app.router.routes.append(route)
