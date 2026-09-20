"""Prueba opt-in: DATABASE_URL en memoria; esquema único eliminado al terminar."""
import os
import sys
import uuid
from pathlib import Path
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import text
import conversation_memory as memory
from db_adapter import get_engine, PostgresConnectionWrapper


def run():
    if not os.environ.get('DATABASE_URL'):
        print('SKIP: PostgreSQL requiere DATABASE_URL')
        return
    schema = 'memory_probe_' + uuid.uuid4().hex
    engine = get_engine()
    created = False
    try:
        with engine.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA {schema}'))
            conn.execute(text(f'SET LOCAL search_path TO {schema}'))
            conn.execute(text(memory.SCHEMA))
        created = True

        @contextmanager
        def isolated_session(_path):
            with engine.begin() as conn:
                conn.execute(text(f'SET LOCAL search_path TO {schema}'))
                yield PostgresConnectionWrapper(conn)

        with patch.object(memory, 'get_db_session', isolated_session):
            store = memory.ConversationMemory(lambda: '', limit=100)
            with ThreadPoolExecutor(max_workers=4) as pool:
                list(pool.map(lambda i: store.add_turn('a', str(i), str(i)), range(12)))
            rows = store.get('a')
            assert len(rows) == 24 and len({r['content'] for r in rows}) == 12
            assert all(rows[i]['content'] == rows[i+1]['content'] for i in range(0,24,2))
            engine.dispose()  # Recuperar memoria usando nuevas conexiones.
            assert memory.ConversationMemory(lambda: '').get('a') == rows
            store.add_turn('b', 'otro usuario', 'respuesta')
            def fail(rows):
                raise RuntimeError('synthetic')
            try:
                store.mutate('a', fail)
            except RuntimeError:
                pass
            assert store.get('a') == rows
            store.limit = 20
            store.add_turn('a', 'limite', 'respuesta')
            assert len(store.get('a')) == 20
            store.clear('a')
            assert store.get('a') == [] and len(store.get('b')) == 2
            print('PASS PostgreSQL: concurrencia, reconexion, aislamiento, limite, borrado y rollback')
    finally:
        if created:
            with engine.begin() as conn:
                conn.execute(text(f'DROP SCHEMA {schema} CASCADE'))
            print('PASS limpieza del esquema aislado')
        engine.dispose()


if __name__ == '__main__':
    try:
        run()
    except Exception as exc:
        print('FAIL PostgreSQL:', type(exc).__name__)
        sys.exit(1)
