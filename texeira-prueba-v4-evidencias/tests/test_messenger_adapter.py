import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
"""Pruebas firmadas de Messenger, sin red ni escrituras del piloto."""
import hashlib
import hmac
import json
from unittest.mock import patch
from fastapi.testclient import TestClient
import app

def run():
    client = TestClient(app.app)
    payload = {'object':'page','entry':[{'messaging':[{
        'sender':{'id':'synthetic-user'},'recipient':{'id':'synthetic-page'},
        'message':{'mid':'synthetic-mid','text':'Hola'}}]}]}
    def send(value, signed=True):
        raw=json.dumps(value).encode()
        headers={'Content-Type':'application/json'}
        if signed:
            headers['X-Hub-Signature-256']='sha256='+hmac.new(b'test-secret',raw,hashlib.sha256).hexdigest()
        return client.post('/webhook',content=raw,headers=headers)
    with patch.object(app,'FB_APP_SECRET',''), patch.object(app,'rag_chain') as rag:
        assert send(payload).status_code==503
        rag.assert_not_called()
    with patch.object(app,'FB_APP_SECRET','test-secret'), \
         patch.object(app.database,'is_duplicate_webhook',return_value=False) as dedup, \
         patch.object(app.database,'log_interaction') as log, \
         patch.object(app,'rag_chain',return_value={'response':'Hola','is_fallback':False}) as rag, \
         patch.object(app,'send_messenger_message',return_value=True) as outbound:
        assert send(payload,False).status_code==403
        dedup.assert_not_called(); rag.assert_not_called(); outbound.assert_not_called()
        assert send(payload).status_code==200
        rag.assert_called_once(); outbound.assert_called_once(); log.assert_called_once()
        assert log.call_args.kwargs['channel']=='messenger'
        dedup.return_value=True
        assert send(payload).json()['dedup'] is True
        assert outbound.call_count==1
        payload['entry'][0]['messaging'][0]['message']['is_echo']=True
        assert send(payload).json()['echo'] is True
        assert outbound.call_count==1
    print('PASS: Messenger sin configuración, firma obligatoria, recepción, envío simulado, duplicado y eco.')

if __name__=='__main__': run()
