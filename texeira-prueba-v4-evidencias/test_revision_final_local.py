"""Reproduce incertidumbre de la muestra real con respuestas guardadas, sin Groq."""
import json
from pathlib import Path
from unittest.mock import patch
import app
import verified_routes
import trial_support

def run():
    evidence=json.loads(Path('EVALUACION_REAL_EXPLORATORIA_20260915.json').read_text(encoding='utf-8'))
    for case in evidence['cases'][2:]:
        ns={'detect_language':app.detect_language,'get_history':lambda uid:[],
            'conversation_history':{},'add_to_history':lambda *args:None}
        verified_routes.install(ns,trial_support,lambda *args:dict(case['result']))
        result=ns['rag_chain'](case['question'],'synthetic')
        assert result['needs_agency_confirmation'] and not result['resolved_autonomously']
    with patch.object(app,'get_llm',side_effect=AssertionError('No LLM')):
        for question,expected in [('help','I can help'),('bye','Goodbye')]:
            assert expected in app.rag_chain(question,user_id='synthetic-social')['response']
    print('PASS: incertidumbre hotel/accesibilidad y ayuda/despedida EN, sin llamadas externas.')

if __name__=='__main__': run()
