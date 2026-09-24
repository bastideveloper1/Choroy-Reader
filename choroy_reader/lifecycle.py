"""Minimal durable identities and history retention timestamps."""
from datetime import datetime, timezone


class Lifecycle:
    def __init__(self, store):
        self.store = store
        with store.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS article_identity (link TEXT PRIMARY KEY, first_seen REAL NOT NULL, retired_at REAL)')

    def remember(self, link, now=None):
        now = datetime.now(timezone.utc).timestamp() if now is None else now
        with self.store.connect() as db:
            db.execute('INSERT OR IGNORE INTO article_identity(link, first_seen) VALUES (?, ?)', (link, now))
            return db.execute('SELECT first_seen, retired_at FROM article_identity WHERE link=?', (link,)).fetchone()

    def retire(self, link, now):
        with self.store.connect() as db:
            db.execute('UPDATE article_identity SET retired_at=? WHERE link=?', (now, link))

    def restore(self, link, now):
        with self.store.connect() as db:
            db.execute('UPDATE article_identity SET first_seen=?, retired_at=NULL WHERE link=?', (now, link))
