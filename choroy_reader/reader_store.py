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

            database.execute('''CREATE TABLE IF NOT EXISTS reader_notes (
                id TEXT PRIMARY KEY, link TEXT NOT NULL, language TEXT NOT NULL,
                body TEXT NOT NULL, data TEXT NOT NULL)''')

            database.execute('CREATE TABLE IF NOT EXISTS reader_images (link TEXT PRIMARY KEY, images TEXT NOT NULL)')

    def read_images(self, link):
        with self.connect() as database:
            row = database.execute('SELECT images FROM reader_images WHERE link=?', (link,)).fetchone()
        return json.loads(row[0]) if row else None

    def save_images(self, link, images):
        with self.connect() as database:
            database.execute('INSERT OR REPLACE INTO reader_images VALUES (?, ?)', (link, json.dumps(images)))

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

    def read_notes(self, link, language, body):
        with self.connect() as database:
            rows = database.execute(
                'SELECT data FROM reader_notes WHERE link=? AND language=? AND body=? ORDER BY rowid',
                (link, language, body)).fetchall()
        return [json.loads(row[0]) for row in rows]

    def save_note(self, link, language, body, note):
        with self.connect() as database:
            database.execute('INSERT INTO reader_notes VALUES (?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET data=excluded.data',
                             (note['id'], link, language, body, json.dumps(note)))

    def delete_note(self, note_id, link, language, body):
        with self.connect() as database:
            database.execute('DELETE FROM reader_notes WHERE id=? AND link=? AND language=? AND body=?',
                             (note_id, link, language, body))

    def note_record(self, note_id):
        with self.connect() as database:
            row = database.execute('SELECT link, language, body, data FROM reader_notes WHERE id=?',
                                   (note_id,)).fetchone()
        return (*row[:3], json.loads(row[3])) if row else None
