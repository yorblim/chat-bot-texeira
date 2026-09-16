"""Configuración cloud sin credenciales reales ni red."""
import tempfile
from pathlib import Path
from runtime_settings import configure

with tempfile.TemporaryDirectory() as tmp:
    keys=('META_VERIFY_TOKEN','META_ACCESS_TOKEN','META_PHONE_NUMBER_ID','META_APP_SECRET')
    env={k:'synthetic-cloud' for k in keys}
    env.update(TEXEIRA_ENABLE_WHATSAPP='true',TEXEIRA_STATE_DIR=tmp,GROQ_API_KEY='synthetic-cloud')
    assert configure(env,{k:'synthetic-local' for k in keys})==(True,False)
    assert all(env[k]=='synthetic-cloud' for k in keys)
    assert env['GROQ_API_KEY']=='synthetic-cloud'
    assert Path(env['SQLITE_DB_PATH']).parent==Path(tmp)
    local={'TEXEIRA_STATE_DIR':tmp}
    configure(local,{k:'synthetic-local' for k in keys})
    assert all(not local[k] for k in keys)
    try:
        configure({'TEXEIRA_ENABLE_WHATSAPP':'true','TEXEIRA_STATE_DIR':tmp},{})
    except RuntimeError: pass
    else: raise AssertionError('Debe rechazar configuración incompleta')
    fb={'TEXEIRA_ENABLE_MESSENGER':'true','TEXEIRA_STATE_DIR':tmp}
    configure(fb,{'META_VERIFY_TOKEN':'synthetic-verify','FB_APP_SECRET':'synthetic-fb'})
    assert fb['META_VERIFY_TOKEN']=='synthetic-verify' and not fb['META_ACCESS_TOKEN']
print('PASS: entorno cloud, aislamiento local, persistencia y configuración incompleta.')
