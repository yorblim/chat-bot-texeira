"""Entrada restringida para servidor continuo; no usar con scale-to-zero.

El ACK se transmite directamente. El procesamiento posterior usa el proceso
actual: no es una cola durable y requiere CPU disponible después del ACK.
"""
import asyncio
import hmac
import logging
import os
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

logger=logging.getLogger(__name__)
app=FastAPI(openapi_url=None,docs_url=None,redoc_url=None)
_state={'ready':False,'local_app':None,'error':None}

def _load_app():
    from app import app as local_app
    return local_app

@app.on_event('startup')
async def startup():
    _state.update(ready=False,local_app=None,error=None)
    try:
        if os.environ.get('K_SERVICE') and not os.environ.get('ALLOW_CLOUD_RUN'):
            raise RuntimeError('Cloud Run no soportado: faltan cola durable y persistencia externa.')
        local=await asyncio.to_thread(_load_app)
        for handler in local.router.on_startup:
            if asyncio.iscoroutinefunction(handler): await handler()
            else: await asyncio.to_thread(handler)
        _state.update(ready=True,local_app=local)
    except Exception:
        _state.update(ready=False,local_app=None,error=True)
        logger.exception('No se pudo iniciar el webhook.')
        raise

@app.on_event('shutdown')
async def shutdown():
    _state['ready']=False
    local=_state.get('local_app')
    if local:
        for handler in local.router.on_shutdown:
            if asyncio.iscoroutinefunction(handler): await handler()
            else: await asyncio.to_thread(handler)
    _state['local_app']=None

@app.get('/healthz')
def health():
    ready=_state['ready'] and _state['local_app'] is not None and not _state['error']
    return JSONResponse({'status':'ok' if ready else 'unavailable'},status_code=200 if ready else 503)

@app.get('/webhook')
async def meta_verify(request:Request):
    expected=os.environ.get('META_VERIFY_TOKEN','')
    token=request.query_params.get('hub.verify_token','')
    challenge=request.query_params.get('hub.challenge','')
    if expected and request.query_params.get('hub.mode')=='subscribe' and challenge and hmac.compare_digest(token.encode(),expected.encode()):
        return Response(challenge,media_type='text/plain')
    return Response(status_code=403)

IMAGES_DIR = os.path.join(os.path.dirname(__file__), "data", "images")

@app.get("/images/{filename}")
async def serve_image(filename: str):
    import re
    from fastapi.responses import FileResponse
    if not re.match(r"^[\w\-\.]+\.(jpg|jpeg|png|webp)$", filename, re.IGNORECASE):
        return Response(status_code=400)
    file_path = os.path.join(IMAGES_DIR, filename)
    if not os.path.exists(file_path):
        return Response(status_code=404)
    return FileResponse(file_path, media_type="image/jpeg")

class ForwardResponse(Response):
    def __init__(self,local_app):
        super().__init__(content=b'')
        self.local_app=local_app

    async def __call__(self,scope,receive,send):
        # No copiar/bufferizar el cuerpo ni esperar BackgroundTasks para emitir ACK.
        await self.local_app(scope,receive,send)

@app.post('/webhook')
async def meta_webhook(request:Request):
    if not _state['ready'] or _state['local_app'] is None or _state['error']:
        return Response(status_code=503,headers={'Retry-After':'10'})
    return ForwardResponse(_state['local_app'])
