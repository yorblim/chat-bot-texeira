"""Regresión de las rutas expuestas detectadas durante la revisión."""
import asyncio
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
from fastapi import FastAPI
import whatsapp_entry as entry


async def main():
    local = FastAPI()

    @local.get('/history/synthetic-user')
    @local.delete('/history/synthetic-user')
    @local.get('/dashboard')
    @local.get('/metrics')
    async def synthetic():
        return {'synthetic': True}

    observations = {}
    with patch.dict(entry._state, ready=True, local_app=local, error=None):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=entry.app), base_url='http://test') as client:
            with patch.dict(os.environ, {'ADMIN_USER': 'synthetic', 'ADMIN_PASSWORD': 'synthetic-password'}):
                for method, path in [('GET', '/dashboard'), ('GET', '/history/synthetic-user'),
                                     ('DELETE', '/history/synthetic-user'), ('GET', '/metrics')]:
                    observations[f'{method} {path} with_auth_configured'] = (await client.request(method, path)).status_code
            with patch.dict(os.environ, {'ADMIN_USER': 'synthetic', 'ADMIN_PASSWORD': '', 'K_SERVICE': 'synthetic'}):
                observations['GET /dashboard missing_password_in_cloud'] = (await client.get('/dashboard')).status_code
    assert observations['GET /dashboard with_auth_configured'] == 401
    assert observations['GET /history/synthetic-user with_auth_configured'] == 401
    assert observations['DELETE /history/synthetic-user with_auth_configured'] == 401
    assert observations['GET /metrics with_auth_configured'] == 401
    assert observations['GET /dashboard missing_password_in_cloud'] == 401
    output = Path(__file__).resolve().parents[1] / 'docs' / 'REGRESION_SEGURIDAD_20260919.json'
    output.write_text(json.dumps({'mode': 'synthetic_no_network', 'observations': observations}, indent=2), encoding='utf-8')
    print(json.dumps(observations, indent=2))
    print('PASS: rutas internas protegidas incluso con configuración incompleta.')


if __name__ == '__main__':
    asyncio.run(main())
