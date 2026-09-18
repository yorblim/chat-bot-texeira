import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
"""Muestra exploratoria con LLM real: máximo cuatro llamadas, sin registros del piloto."""
import contextlib,io,json,os,time,hashlib
from pathlib import Path
os.environ['HF_HUB_OFFLINE']='1'
os.environ['TRANSFORMERS_OFFLINE']='1'
os.environ['ANONYMIZED_TELEMETRY']='False'
import app

CASES=[
 {'id':'new-es-comparison','language':'es','question':'Compara Humantay y Montaña de 7 Colores según los servicios del folleto.',
  'criteria':'Ambos: transporte turístico, guía, desayuno y almuerzo según F1. No inventar precios, cupos ni igualdad de horarios.'},
 {'id':'new-en-train','language':'en','question':'Please summarize the services for a visitor taking the Machu Picchu train tour.',
  'criteria':'English. Transfer Cusco–Ollanta–Cusco, return train, bus up/down, entrance, guide; hotel pickup in F3. No invented meal/hotel night.'},
 {'id':'new-es-hotel','language':'es','question':'¿Cuál es el nombre exacto del hotel donde dormiré con el tour Machu Picchu en tren?',
  'criteria':'No hay hotel ni pernocte documentado para esta modalidad. No inventar nombre ni convertir recojo del hotel en alojamiento incluido.'},
 {'id':'new-en-access','language':'en','question':'Tell me whether the Humantay excursion can accommodate a wheelchair throughout the entire trip.',
  'criteria':'English. No accessibility guarantee documented. Require confirmation; no invented arrangements or confident suitability claim.'},
]

def main():
    if app.LLM_PROVIDER!='groq': raise SystemExit('Proveedor distinto del esperado; no se hicieron llamadas.')
    from langchain_openai import ChatOpenAI
    llm=ChatOpenAI(model=app.LLM_MODEL,temperature=.1,max_tokens=900,
        api_key=os.environ['GROQ_API_KEY'],base_url=os.environ.get('GROQ_API_BASE','https://api.groq.com/openai/v1'),
        timeout=45,max_retries=0)
    rows=[];calls=[];retrieved=[]
    class LLM:
        def invoke(self,messages):
            if len(calls)>=4:raise RuntimeError('Call budget exceeded')
            formatted=[{'type':m[0],'content':m[1]} if isinstance(m,(tuple,list)) else
                       {'type':getattr(m,'type','unknown'),'content':m.content} for m in messages]
            call={'number':len(calls)+1,'input_messages':formatted};calls.append(call)
            try:
                answer=llm.invoke(messages);call['usage']=getattr(answer,'usage_metadata',None)
                call['raw_answer']=answer.content;call['status']='completed';return answer
            except Exception as e:
                call['status']='provider_error';call['error_type']=type(e).__name__;raise
    original_get=app.get_retriever
    class Retriever:
        def invoke(self,q):
            docs=original_get().invoke(q)
            retrieved.extend({'text':d.page_content,'metadata':d.metadata} for d in docs)
            return docs
    app.get_llm=lambda:LLM()
    app.get_retriever=lambda:Retriever()
    # rag_chain no registra interacciones SQLite. Usuarios sintéticos solo en memoria.
    path=Path('EVALUACION_REAL_EXPLORATORIA_20260915.json')
    for case in CASES:
        retrieved.clear();start=time.perf_counter();before=len(calls)
        with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
            result=app.rag_chain(case['question'],user_id='eval-'+case['id'])
        row={**case,'result':result,'retrieved':list(retrieved),'calls':calls[before:],
             'elapsed_ms':round((time.perf_counter()-start)*1000,2),'review_status':'pending'}
        rows.append(row)
        path.write_text(json.dumps({'mode':'exploratory_real_llm','provider':app.LLM_PROVIDER,'model':app.LLM_MODEL,
            'total_llm_calls':len(calls),'cases':rows,'code_sha256':hashlib.sha256(Path('app.py').read_bytes()).hexdigest()},ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({'id':case['id'],'route':result.get('response_route'),'llm_calls':len(calls)-before,
                          'provider_error':any(c.get('status')=='provider_error' for c in calls[before:])}),flush=True)
        if any(c.get('status')=='provider_error' for c in calls[before:]):break

if __name__=='__main__':main()
