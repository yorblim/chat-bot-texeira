"""Entorno del servidor con prioridad sobre la configuración local."""
import os
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def configure(env=None, values=None):
    env=os.environ if env is None else env
    if values is None:
        from dotenv import dotenv_values
        values=dotenv_values(ROOT.parent/'texeira-chatbot'/'.env')
    for key in ('LLM_PROVIDER','LLM_MODEL','GROQ_API_KEY','GROQ_API_BASE','OPENAI_API_KEY','ANTHROPIC_API_KEY','DEEPSEEK_API_KEY'):
        if key not in env and values.get(key): env[key]=values[key]
    wa=env.get('TEXEIRA_ENABLE_WHATSAPP','false').lower()=='true'
    fb=env.get('TEXEIRA_ENABLE_MESSENGER','false').lower()=='true'
    groups=[(wa,('META_ACCESS_TOKEN','META_PHONE_NUMBER_ID','META_APP_SECRET','WHATSAPP_TEST_BSUID_MAP','WHATSAPP_TEST_MODE')),
            (fb,('FB_PAGE_ACCESS_TOKEN','FB_APP_SECRET')),(wa or fb,('META_VERIFY_TOKEN',))]
    for enabled,keys in groups:
        for key in keys:
            env[key]=env.get(key,values.get(key) or '') if enabled else ''
    if wa and not all(env.get(k) for k in ('META_VERIFY_TOKEN','META_ACCESS_TOKEN','META_PHONE_NUMBER_ID','META_APP_SECRET')):
        raise RuntimeError('Configuración WhatsApp incompleta; revisar variables protegidas del servidor.')
    state=Path(env.get('TEXEIRA_STATE_DIR',str(ROOT)))
    state.mkdir(parents=True,exist_ok=True)
    env.setdefault('SQLITE_DB_PATH',str(state/'trial_logs.db'))
    env.setdefault('CHROMA_HYBRID_DIR',str(ROOT/'chroma_f1_confirmado_20260915_db'))
    return wa,fb

def state_file(name):
    root=Path(os.environ.get('TEXEIRA_STATE_DIR',str(ROOT)))
    root.mkdir(parents=True,exist_ok=True)
    return root/name
