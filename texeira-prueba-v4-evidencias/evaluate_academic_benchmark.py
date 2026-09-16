"""Recolección local SIMULADA para revisión humana; no es pretest/postest."""
import asyncio
import contextlib
import io
import json
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

os.environ['HF_HUB_OFFLINE']='1'
os.environ['TRANSFORMERS_OFFLINE']='1'
os.environ['ANONYMIZED_TELEMETRY']='False'
import app
import handoff_support

def run_benchmark(bank_path='BANCO_EVALUACION_ACADEMICA.json', output_path='RESULTADOS_EVALUACION_ACADEMICA.json'):
    bank=json.loads(Path(bank_path).read_text(encoding='utf-8'))
    rows=[]
    class MockLLM:
        def invoke(self,messages):
            return type('Answer',(),{'content':'[SIMULACIÓN: no se evaluó generación real.]','usage_metadata':None})()
    with tempfile.TemporaryDirectory() as tmp, \
         patch.object(handoff_support,'DB',Path(tmp)/'requests.db'), \
         patch.object(handoff_support,'notify_advisor',return_value=False), \
         patch.object(app.database,'log_interaction'), \
         patch.object(app,'get_llm',return_value=MockLLM()), \
         patch.object(app,'conversation_history',{}):
        for case in bank['cases']:
            start=time.perf_counter()
            with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
                response=asyncio.run(app.test_chat(app.TestChatRequest(user_id='benchmark-'+case['id'],message=case['question'])))
            data=json.loads(response.body)
            rows.append({'id':case['id'],'question':case['question'],'language':case['language'],
                'criteria_for_human_review':case['ground_truth_criteria'],
                'response':data.get('response'),'actual_route':data.get('response_route'),
                'elapsed_local_simulated_ms':round((time.perf_counter()-start)*1000,2),
                'reported_resolved':data.get('resolved_autonomously'),
                'handoff_registered':data.get('escalated_to_human'),
                'needs_agency_confirmation':data.get('needs_agency_confirmation'),
                'human_review_status':'pending','passed':None})
    summary={'mode':'local_simulation_not_academic_validation','total_cases':len(rows),
        'real_llm_calls':0,'approved_cases':None,'metrics_thesis':None,
        'limitations':['No mide precisión, entrega, resolución validada ni latencia real de LLM.',
                      'Criterios y respuestas requieren revisión humana; banco ya usado para ajustes, no conjunto independiente.'],
        'cases':rows}
    Path(output_path).write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'Recolección local: {len(rows)} casos; calificación humana pendiente. Sin métricas de tesis.')
    return summary

if __name__=='__main__': run_benchmark()
