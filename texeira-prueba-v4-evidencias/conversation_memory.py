"""Memoria acotada por usuario; escrituras serializadas en SQLite y PostgreSQL."""
import json
import time
from contextlib import contextmanager
from contextvars import ContextVar

from db_adapter import get_db_session, is_postgres

SCHEMA = """CREATE TABLE IF NOT EXISTS conversation_memory (
    user_id TEXT PRIMARY KEY, messages TEXT NOT NULL
)"""
_suspended = ContextVar('conversation_memory_suspended', default=False)


@contextmanager
def suspend_recording():
    """El wrapper guarda la respuesta definitiva, no la respuesta intermedia."""
    token = _suspended.set(True)
    try:
        yield
    finally:
        _suspended.reset(token)


class ConversationMemory:
    def __init__(self, path, limit=20):
        self.path = path
        self.limit = limit

    @contextmanager
    def session(self):
        with get_db_session(self.path()) as conn:
            if not is_postgres():
                conn.execute(SCHEMA)
            yield conn

    def get(self, user_id, default=None):
        with self.session() as conn:
            row = conn.execute('SELECT messages FROM conversation_memory WHERE user_id=?', (user_id,)).fetchone()
            return json.loads(row[0]) if row else ([] if default is None else default)

    def mutate(self, user_id, change):
        with self.session() as conn:
            if not is_postgres():
                conn.execute('BEGIN IMMEDIATE')
            conn.execute("INSERT INTO conversation_memory (user_id, messages) VALUES (?, ?) ON CONFLICT (user_id) DO NOTHING", (user_id, '[]'))
            suffix = ' FOR UPDATE' if is_postgres() else ''
            row = conn.execute('SELECT messages FROM conversation_memory WHERE user_id=?' + suffix, (user_id,)).fetchone()
            messages = change(json.loads(row[0]))[-self.limit:]
            conn.execute('UPDATE conversation_memory SET messages=? WHERE user_id=?', (json.dumps(messages, ensure_ascii=False), user_id))

    def append(self, user_id, role, content):
        if not _suspended.get():
            self.mutate(user_id, lambda messages: messages + [dict(role=role, content=content, timestamp=time.time())])

    def clear(self, user_id):
        self.mutate(user_id, lambda messages: [])

    def add_turn(self, user_id, question, response):
        if not _suspended.get():
            now = time.time()
            self.mutate(user_id, lambda messages: messages + [
                dict(role='human', content=question, timestamp=now),
                dict(role='ai', content=response, timestamp=now),
            ])

    def update_last_response(self, user_id, content):
        def update(messages):
            if messages and messages[-1]['role'] == 'ai':
                messages[-1]['content'] = content
            return messages
        self.mutate(user_id, update)
