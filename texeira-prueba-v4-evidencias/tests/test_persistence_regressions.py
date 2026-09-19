"""Regresiones aisladas de persistencia; no acceden a servicios externos."""
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import database
import db_adapter
from sqlalchemy import create_engine


class PersistenceRegressions(unittest.TestCase):
    def test_cursor_supports_iteration_used_by_metrics(self):
        engine = create_engine('sqlite:///:memory:')
        with engine.connect() as conn:
            cursor = db_adapter.PostgresConnectionWrapper(conn).execute('SELECT 3 AS n')
            self.assertEqual([dict(row) for row in cursor], [{'n': 3}])
        engine.dispose()

    def test_commit_failure_is_visible_and_connection_closed(self):
        raw = Mock()
        raw.commit.side_effect = RuntimeError('commit failed')
        with self.assertRaisesRegex(RuntimeError, 'commit failed'):
            with db_adapter.PostgresConnectionWrapper(raw):
                pass
        raw.close.assert_called_once()

    def test_partial_unique_index_allows_idempotent_retry(self):
        engine = create_engine('sqlite:///:memory:')
        with engine.connect() as raw:
            conn = db_adapter.PostgresConnectionWrapper(raw)
            conn.execute('CREATE TABLE interactions (id INTEGER PRIMARY KEY, client_message_id TEXT)')
            conn.execute('CREATE UNIQUE INDEX idx ON interactions(client_message_id) WHERE client_message_id IS NOT NULL')
            first = conn.execute('INSERT OR IGNORE INTO interactions (client_message_id) VALUES (?)', ('message',))
            self.assertEqual(first.lastrowid, 1)
            retry = conn.execute('INSERT OR IGNORE INTO interactions (client_message_id) VALUES (?)', ('message',))
            self.assertEqual(retry.rowcount, 0)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM interactions').fetchone()[0], 1)
        engine.dispose()

    def test_database_paths_are_isolated_and_connections_released(self):
        with patch.dict(os.environ, {'DATABASE_URL': ''}), tempfile.TemporaryDirectory() as tmp:
            one, two = str(Path(tmp) / 'one.db'), str(Path(tmp) / 'two.db')
            database.init_db(one)
            database.init_db(two)
            self.assertFalse(database.is_duplicate_webhook('same-id', db_path=one))
            self.assertFalse(database.is_duplicate_webhook('same-id', db_path=two))
            self.assertTrue(database.is_duplicate_webhook('same-id', db_path=one))

    def test_storage_failure_is_not_reported_as_duplicate(self):
        with patch.dict(os.environ, {'DATABASE_URL': ''}), tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / 'missing-schema.db')
            with self.assertRaises(sqlite3.OperationalError):
                database.is_duplicate_webhook('new-id', db_path=path)

    def test_adapter_flow_returns_connections_to_pool(self):
        # SQLite ejecuta el SQL adaptado; no sustituye integración PostgreSQL real.
        with patch.dict(os.environ, {'DATABASE_URL': ''}), tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / 'pool.db')
            database.init_db(path)
            engine = create_engine('sqlite:///' + path, pool_size=1, max_overflow=0, pool_timeout=0.1)
            try:
                with patch.object(db_adapter, 'is_postgres', return_value=True), \
                     patch.object(db_adapter, 'ensure_postgres_schema'), \
                     patch.object(db_adapter, 'get_engine', return_value=engine):
                    args = dict(user_id='test', channel='test', detected_language='es',
                                user_message='hola', bot_response='hola', resolved_autonomously=True,
                                latency_ms=1, escalated_to_human=False, client_message_id='retry')
                    first = database.log_interaction(**args)
                    self.assertGreater(first, 0)
                    self.assertEqual(database.log_interaction(**args), first)
                    self.assertEqual(database.get_metrics_summary()['total_interactions'], 1)
                    self.assertEqual(len(database.get_recent_interactions()), 1)
                    self.assertFalse(database.is_duplicate_webhook('webhook'))
                    self.assertTrue(database.is_duplicate_webhook('webhook'))
                    self.assertEqual(engine.pool.checkedout(), 0)
                    with self.assertRaisesRegex(RuntimeError, 'abort'):
                        with db_adapter.get_db_session() as conn:
                            conn.execute('DELETE FROM interactions')
                            raise RuntimeError('abort')
                    self.assertEqual(database.get_metrics_summary()['total_interactions'], 1)
                    self.assertEqual(engine.pool.checkedout(), 0)
            finally:
                engine.dispose()


if __name__ == '__main__':
    unittest.main()
