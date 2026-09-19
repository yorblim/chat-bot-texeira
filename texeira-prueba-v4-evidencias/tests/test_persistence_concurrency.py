"""Mismos contratos sobre SQLite o PostgreSQL local dedicado (puerto 55439)."""
import os
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import database
import db_adapter
import handoff_support as handoff
import operational_metrics


def run():
    url = os.getenv('TEST_DATABASE_URL', '')
    if url:
        from sqlalchemy.engine import make_url
        parsed = make_url(url)
        assert parsed.host in {'127.0.0.1', 'localhost'} and parsed.port == 55439
        assert parsed.database == 'postgres' and parsed.username == 'codex_test'
    with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, DATABASE_URL=url):
        db = str(Path(tmp) / 'interactions.db')
        with patch.object(handoff, 'DB', Path(tmp) / 'handoffs.db'), \
             patch.object(operational_metrics, 'DB', Path(tmp) / 'metrics.db'):
            database.init_db(db)
            # Preparar tabla SQLite antes de la carrera; PostgreSQL usa su esquema común.
            with handoff.connection():
                pass
            with ThreadPoolExecutor(max_workers=8) as pool:
                requests = list(pool.map(lambda _: handoff.create_request('concurrent', 'whatsapp', 'asesor', []), range(8)))
            assert sum(created for _, created in requests) == 1
            assert len({row['id'] for row, _ in requests}) == 1
            ticket = requests[0][0]['id']
            handoff.update_request(ticket, 'in_progress', 'synthetic', '')
            handoff.update_request(ticket, 'closed', 'synthetic', 'resuelto')
            assert handoff.create_request('concurrent', 'whatsapp', 'otra consulta', [])[1]
            with ThreadPoolExecutor(max_workers=8) as pool:
                claims = list(pool.map(lambda _: database.claim_webhook('same', 'user', db), range(8)))
            assert sum(state == 'claimed' for state, _ in claims) == 1
            assert sum(state == 'busy' for state, _ in claims) == 7
            owner = next(owner for state, owner in claims if state == 'claimed')
            database.finish_webhook('same', owner, False, db)
            state, new_owner = database.claim_webhook('same', 'user', db)
            assert state == 'claimed' and new_owner != owner
            database.finish_webhook('same', new_owner, True, db)
            assert database.claim_webhook('same', 'user', db)[0] == 'completed'
            _, expired = database.claim_webhook('expired', 'user', db, lease_seconds=-1)
            state, replacement = database.claim_webhook('expired', 'user', db)
            assert state == 'claimed' and expired != replacement
            try:
                database.renew_webhook('expired', expired, db)
            except RuntimeError:
                pass
            else:
                raise AssertionError('Un intento vencido no puede enviar mensajes')
            args = dict(user_id='user', channel='test', detected_language='es', user_message='hola',
                        bot_response='hola', resolved_autonomously=True, latency_ms=1,
                        escalated_to_human=False, client_message_id='interaction', db_path=db)
            first = database.log_interaction(**args)
            assert first > 0 and database.log_interaction(**args) == first
            assert database.get_metrics_summary(db)['total_interactions'] == 1
            event = operational_metrics.start()
            operational_metrics.finish(event, 'api_accepted', 10, 20)
            assert operational_metrics.summary()['api_accepted'] == 1
            assert operational_metrics.summary()['human_requests']['pending'] == 1
            print('PASS: concurrencia, reintentos, lease, ID de interacción y métricas en ' + ('PostgreSQL real' if url else 'SQLite'))
    if db_adapter._ENGINE is not None:
        assert db_adapter._ENGINE.pool.checkedout() == 0
        db_adapter._ENGINE.dispose()


if __name__ == '__main__':
    run()
