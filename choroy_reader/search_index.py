"""Disposable SQLite FTS5 index with literal, accent-insensitive substring search."""
import sqlite3
import threading
from .library import normalize_text


class SearchIndex:
    def __init__(self, use_fts=True):
        self.lock = threading.RLock()
        self.db = sqlite3.connect(':memory:', check_same_thread=False)
        self.documents = {}
        self.available = False
        if use_fts:
            try:
                self.db.execute("CREATE VIRTUAL TABLE search USING fts5(link UNINDEXED, title, body, tokenize='trigram')")
                self.available = True
            except sqlite3.OperationalError:
                pass

    def match(self, documents, query, include_body=False):
        """Synchronize only changed rows; retain exactly the current collection."""
        query = normalize_text(query.strip())
        with self.lock:
            current = {link: (normalize_text(title), normalize_text(body)) for link, title, body in documents}
            if self.available:
                with self.db:
                    for link in self.documents.keys() - current.keys():
                        self.db.execute('DELETE FROM search WHERE link=?', (link,))
                    for link, values in current.items():
                        if self.documents.get(link) != values:
                            self.db.execute('DELETE FROM search WHERE link=?', (link,))
                            self.db.execute('INSERT INTO search VALUES (?,?,?)', (link, *values))
            self.documents = current
            if self.available and len(query) >= 3:
                phrase = '"' + query.replace('"', '""') + '"'
                if not include_body:
                    phrase = 'title : ' + phrase
                return {row[0] for row in self.db.execute('SELECT link FROM search WHERE search MATCH ?', (phrase,))}
            return {link for link, (title, body) in current.items()
                    if query in title or (include_body and query in body)}

    def close(self):
        with self.lock:
            self.db.close()
