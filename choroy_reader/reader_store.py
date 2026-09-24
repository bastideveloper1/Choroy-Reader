"""Durable reader snapshots, translations and language-specific annotations."""
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path


class ReaderStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as database:
            database.execute('''CREATE TABLE IF NOT EXISTS reader_state (
                link TEXT PRIMARY KEY, original TEXT NOT NULL,
                translation TEXT, original_marks TEXT NOT NULL DEFAULT '[]',
                translated_marks TEXT NOT NULL DEFAULT '[]')''')

    @contextmanager
    def connect(self):
        database = sqlite3.connect(self.path, timeout=15)
        try:
            with database:
                yield database
        finally:
            database.close()

    def read(self, link):
        with self.connect() as database:
            row = database.execute('SELECT original, translation, original_marks, translated_marks FROM reader_state WHERE link=?', (link,)).fetchone()
        if not row:
            return None
        return dict(original=row[0], translation=row[1],
                    original_marks=json.loads(row[2]), translated_marks=json.loads(row[3]))

    def save_original(self, link, body):
        # Never move offsets onto a different revision of an article.
        with self.connect() as database:
            database.execute('INSERT OR IGNORE INTO reader_state(link, original) VALUES (?, ?)', (link, body))

    def save_translation(self, link, original, translation):
        self.save_original(link, original)
        with self.connect() as database:
            database.execute('UPDATE reader_state SET translation=? WHERE link=? AND original=?', (translation, link, original))

    def save_marks(self, link, language, body, marks):
        column = 'translated_marks' if language == 'es' else 'original_marks'
        body_column = 'translation' if language == 'es' else 'original'
        with self.connect() as database:
            database.execute(f'UPDATE reader_state SET {column}=? WHERE link=? AND {body_column}=?',
                             (json.dumps(marks), link, body))
