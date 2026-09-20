"""Persistencia real, aislamiento, concurrencia y rollback sin servicios externos."""
import os
import sys
import json
import subprocess
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from conversation_memory import ConversationMemory, suspend_recording


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'DATABASE_URL': ''})
        self.env.start()
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name) / 'memory.db')
        self.memory = ConversationMemory(lambda: self.path)

    def tearDown(self):
        self.tmp.cleanup()
        self.env.stop()

    def test_survives_new_process(self):
        self.memory.add_turn('a', 'Cusco', 'Respuesta')
        code = 'import sys,json; from conversation_memory import ConversationMemory; print(json.dumps(ConversationMemory(lambda:sys.argv[1]).get("a")))'
        result = subprocess.run([sys.executable, '-c', code, self.path], cwd=ROOT, capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(result.stdout), self.memory.get('a'))

    def test_isolation_clear_and_limit(self):
        self.memory.add_turn('b', 'privado', 'respuesta')
        for i in range(14):
            self.memory.add_turn('a', str(i), str(i))
        self.assertEqual(len(self.memory.get('a')), 20)
        self.assertEqual(self.memory.get('a')[0]['content'], '4')
        self.memory.clear('a')
        self.assertEqual(self.memory.get('a'), [])
        self.assertEqual(len(self.memory.get('b')), 2)

    def test_concurrent_writers_keep_complete_turns(self):
        self.memory.limit = 100
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda i: self.memory.add_turn('a', str(i), str(i)), range(30)))
        rows = self.memory.get('a')
        self.assertEqual(len(rows), 60)
        self.assertEqual(len({r['content'] for r in rows}), 30)
        for i in range(0, 60, 2):
            self.assertEqual(rows[i]['content'], rows[i+1]['content'])
            self.assertEqual([rows[i]['role'], rows[i+1]['role']], ['human', 'ai'])

    def test_rollback_and_detached_reads(self):
        self.memory.add_turn('a', 'hola', 'respuesta')
        before = self.memory.get('a')
        def fail(messages):
            messages.clear()
            raise RuntimeError('synthetic failure')
        with self.assertRaises(RuntimeError):
            self.memory.mutate('a', fail)
        self.assertEqual(self.memory.get('a'), before)
        before.clear()
        self.assertEqual(len(self.memory.get('a')), 2)

    def test_suspension_and_final_response(self):
        with self.assertRaises(RuntimeError):
            with suspend_recording():
                self.memory.append('a', 'ai', 'intermedia')
                raise RuntimeError('synthetic')
        self.assertEqual(self.memory.get('a'), [])
        self.memory.add_turn('a', 'hola', 'respuesta')
        self.memory.update_last_response('a', 'definitiva')
        self.assertEqual(self.memory.get('a')[-1]['content'], 'definitiva')

    def test_app_routes_persist_without_duplicate_messages(self):
        import app
        with patch.object(app, 'SQLITE_DB_PATH', self.path):
            result = app.rag_chain('Hola', 'route-user')
            self.assertEqual(len(app.get_history('route-user')), 2)
            self.assertEqual(app.get_history('route-user')[-1]['content'], result['response'])
            app.clear_history('route-user')
            self.assertEqual(app.get_history('route-user'), [])

    def test_wrapped_rag_records_only_final_pair(self):
        import app
        import verified_routes
        import trial_support
        with patch.object(app, 'SQLITE_DB_PATH', self.path):
            ns = dict(vars(app))
            def original(question, user_id):
                app.add_to_history(user_id, 'human', question)
                app.add_to_history(user_id, 'ai', 'intermedia')
                return dict(response='respuesta final')
            verified_routes.install(ns, trial_support, original)
            ns['rag_chain']('consulta sintetica xyz', 'rag-user')
            rows = app.get_history('rag-user')
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[-1]['content'], 'respuesta final')

    def test_handoff_final_text_is_persisted(self):
        import app
        import handoff_support
        with patch.object(app, 'SQLITE_DB_PATH', self.path):
            ns = dict(vars(app))
            def original(question, user_id):
                app.add_history_turn(user_id, question, 'Necesita confirmacion')
                return dict(response='Necesita confirmacion', needs_agency_confirmation=True)
            ns['rag_chain'] = original
            handoff_support.install(ns)
            result = ns['rag_chain']('consulta sintetica', 'handoff-user')
            self.assertEqual(app.get_history('handoff-user')[-1]['content'], result['response'])


if __name__ == '__main__':
    unittest.main()
