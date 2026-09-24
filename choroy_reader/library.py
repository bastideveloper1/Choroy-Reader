"""Persistencia local y búsqueda de artículos, sin dependencias de interfaz."""
import base64
import hashlib
import json
import os
import re
import tempfile
import unicodedata
from pathlib import Path
from datetime import datetime


def normalize_text(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.casefold())
                   if unicodedata.category(c) != 'Mn')


def find_matches(text, query):
    query = normalize_text(query.strip())
    if not query:
        return []
    # Conserva posiciones del texto original incluso con acentos compuestos.
    letters, positions = [], []
    for i, letter in enumerate(text):
        for c in normalize_text(letter):
            letters.append(c)
            positions.append(i)
    return [(positions[m.start()], positions[m.end() - 1] + 1)
            for m in re.finditer(re.escape(query), ''.join(letters))]


def score_radar(title, body, words, equivalents=None, details=False):
    text = normalize_text(title + '\n' + body)
    equivalents = equivalents or {}
    interests, mentions = 0, 0
    detected = {}
    seen = set()
    for word in words:
        key = normalize_text(word.strip())
        if not key or key in seen:
            continue
        seen.add(key)
        terms = {normalize_text(p.strip()) for p in [word, *equivalents.get(word, [])] if p.strip()}
        pattern = r'(?<!\w)(?:' + '|'.join(re.escape(p) for p in sorted(terms, key=len, reverse=True)) + r')(?!\w)'
        matches = re.findall(pattern, text)
        count = len(matches)
        labels = {normalize_text(p.strip()): p.strip() for p in [word, *equivalents.get(word, [])] if p.strip()}
        for match in set(matches):
            label = labels[match]
            detected[label] = max(detected.get(label, 0), matches.count(match))
        interests += bool(count)
        mentions += count
    ranked = sorted(detected, key=lambda label: (-detected[label], label.casefold()))
    return (interests, mentions, [f"{label} ({detected[label]})" for label in ranked]) if details else (interests, mentions)


class Library:
    def __init__(self, root):
        self.root = Path(root)

    def path(self, kind, link):
        if kind not in {'guardados', 'descargas', 'archivados', 'feed', 'historial', 'retirados'}:
            raise ValueError('Sección no válida')
        return self.root / kind / (hashlib.sha256(link.encode()).hexdigest() + '.json')

    def contains(self, kind, link):
        return self.path(kind, link).is_file()

    def save(self, kind, article):
        data = {k: article.get(k) for k in ('titulo', 'titulo_es', 'link', 'fuente', 'cuerpo', 'estado_contenido', 'idioma_original', 'traducir_es', 'source_url')}
        if not data['link']:
            raise ValueError('Artículo sin enlace')
        if kind == 'descargas' and not data['cuerpo']:
            raise ValueError('No hay texto disponible para descargar')
        date = article.get('fecha')
        data['fecha'] = date.isoformat() if isinstance(date, datetime) else date
        data['imagen'] = base64.b64encode(article.get('imagen') or b'').decode()
        path = self.path(kind, data['link'])
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as f:
                temporary = f.name
                json.dump(data, f, ensure_ascii=False)
            os.replace(temporary, path)
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)

    def read_path(self, path):
        data = json.loads(Path(path).read_text(encoding='utf-8'))
        data['imagen'] = base64.b64decode(data.get('imagen') or '') or None
        try:
            data['fecha'] = datetime.fromisoformat(data['fecha']) if data.get('fecha') else None
        except (ValueError, TypeError):
            data['fecha'] = None
        return data

    def read(self, kind, link):
        try:
            return self.read_path(self.path(kind, link))
        except (OSError, ValueError, TypeError):
            return None

    def list_items(self, kind):
        self.path(kind, '')  # Valida la sección.
        output = []
        for path in sorted((self.root / kind).glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                output.append(self.read_path(path))
            except (OSError, ValueError, TypeError):
                continue
        return output

    def delete(self, kind, link):
        self.path(kind, link).unlink(missing_ok=True)
