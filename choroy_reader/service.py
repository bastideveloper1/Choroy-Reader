"""Servicios y estado persistente, independientes de la interfaz gráfica."""
import copy
import hashlib
import io
import json
import os
import tempfile
import re
import time
import textwrap
import urllib.parse
from html import unescape
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from PIL import Image
from choroy_reader.library import Library, find_matches, score_radar
from . import core
from .reader_store import ReaderStore


class Service:
    def __init__(self, root):
        self.root = Path(root)
        self.config_path = self.root / 'config.json'
        if self.config_path.exists():
            self.config = json.loads(self.config_path.read_text(encoding='utf-8'))
            if not isinstance(self.config.get('categorias'), list):
                raise ValueError('La configuración no contiene una lista de categorías válida')
        else:
            self.config = copy.deepcopy(core.DEFAULT_CONFIG)
        self.config.setdefault('color', self.config.get('tema', 'gris'))
        self.config.setdefault('radar_palabras', [])
        self.library = Library(self.root / 'biblioteca')
        self.articles = {}
        self.content = {}
        self.reader_store = ReaderStore(self.root / "reader_state.sqlite3")
        self.seen = set(self.config.get('vistos', []))

    def save_config(self):
        self.root.mkdir(parents=True, exist_ok=True)
        self.config['vistos'] = sorted(self.seen)
        name = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=self.root, delete=False) as f:
                name = f.name
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            os.replace(name, self.config_path)
        finally:
            if name and os.path.exists(name):
                os.unlink(name)

    def image_url(self, data):
        if not data:
            return ''
        folder = self.root / 'cache' / 'images'
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / (hashlib.sha256(data).hexdigest() + '.png')
        if not path.exists():
            try:
                with Image.open(io.BytesIO(data)) as image:
                    image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
                    out = io.BytesIO()
                    image.convert('RGBA').save(out, 'PNG')
                path.write_bytes(out.getvalue())
            except Exception:
                return ''
        return path.as_uri()

    def fetch_image(self, link, image_url=None):
        candidates = [urllib.parse.urljoin(link, unescape(image_url))] if image_url else []
        for candidate in candidates:
            try:
                data = core.download(candidate, timeout=8)
                with Image.open(io.BytesIO(data)) as image:
                    image.verify()
                return data
            except Exception:
                pass
        candidate = core.get_open_graph_image(link)
        if candidate:
            try:
                data = core.download(candidate, timeout=8)
                with Image.open(io.BytesIO(data)) as image:
                    image.verify()
                return data
            except Exception:
                pass
        return None

    def favicon_path(self, url):
        return self.root / 'cache' / 'favicons' / (hashlib.sha256(url.encode()).hexdigest() + '.png')

    def favicon_url(self, source):
        custom = source.get('favicon_personalizado')
        path = Path(custom) if custom else self.favicon_path(source['url'])
        return path.resolve().as_uri() if path.is_file() else ''

    def fetch_favicon(self, source):
        path = self.favicon_path(source['url'])
        if path.is_file() or source.get('favicon_personalizado'):
            return
        candidates = []
        try:
            from bs4 import BeautifulSoup
            html = core.download(source['url'], timeout=6).decode('utf-8', errors='replace')
            soup = BeautifulSoup(html, 'html.parser')
            candidates = [urllib.parse.urljoin(source['url'], node['href'])
                          for node in soup.find_all('link', href=True)
                          if 'icon' in ' '.join(node.get('rel', [])).lower()]
        except Exception:
            pass
        candidates.append(urllib.parse.urljoin(source['url'], '/favicon.ico'))
        for candidate in candidates[:4]:
            if urllib.parse.urlparse(candidate).scheme not in {'http', 'https'}:
                continue
            try:
                data = core.download(candidate, timeout=6)
                with Image.open(io.BytesIO(data)) as icon:
                    icon.thumbnail((64, 64), Image.Resampling.LANCZOS)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    icon.convert('RGBA').save(path, 'PNG')
                return
            except Exception:
                continue

    def fetch_source(self, source, config):
        source = copy.deepcopy(source)
        self.fetch_favicon(source)
        if source.get('source_type') == 'shortcut':
            source['sin_feed'] = False
            return source, []
        feed = source.get('url_feed') or core.discover_feed(source['url'])
        source['url_feed'] = feed
        if not feed:
            # Una portada inaccesible es un error temporal, no ausencia de RSS.
            core.download(source['url'], timeout=10)
            source['sin_feed'] = True
            return source, []
        source['sin_feed'] = False
        raw = core.get_articles(feed, maximum=source.get('max_articulos') or core.ARTICLES_PER_SOURCE)
        if raw is None:
            raise ValueError('No se pudo descargar el feed')
        output = []
        for title, link, image, date in raw:
            translate = (config.get('mostrar_titulo_es', True) and source.get('modo_titulo', 'en_es') != 'solo_ingles'
                         and source.get('traduccion_es', True))
            translated = core.translate_text(title, skip_spanish=True) if translate else ''
            if translated and ' '.join(translated.casefold().split()) == ' '.join(title.casefold().split()):
                translated = ''
            output.append(dict(titulo=title, titulo_es=translated or '', link=link,
                               imagen=self.fetch_image(link, image), fecha=core.parse_date(date),
                               fuente=source['nombre'], source_url=source['url'], traducir_es=translate))
        return source, output

    def refresh(self, progress=None):
        config = copy.deepcopy(self.config)
        sources = {s['url']: s for c in config['categorias'] for s in c['sitios']}
        results, updated, errors = {}, {}, []
        with ThreadPoolExecutor(max_workers=6) as pool:
            tasks = {pool.submit(self.fetch_source, s, config): url for url, s in sources.items()}
            for number, task in enumerate(as_completed(tasks), 1):
                url = tasks[task]
                try:
                    source, articles = task.result()
                    results[url], updated[url] = articles, source
                except Exception as e:
                    errors.append(f"{sources[url]['nombre']}: {e}")
                if progress:
                    progress(number, len(tasks))
        return results, updated, errors

    def apply_refresh(self, result):
        articles, updated, errors = result
        self.articles.update(articles)
        for category in self.config['categorias']:
            for source in category['sitios']:
                if source['url'] in updated:
                    source['url_feed'] = updated[source['url']].get('url_feed')
                    source['sin_feed'] = updated[source['url']].get('sin_feed', False)
                    source['ultima_actualizacion'] = time.time()
        self.save_config()
        return errors

    def all_articles(self):
        articles = {}
        for category in self.config['categorias']:
            for source in category['sitios']:
                if source.get('source_type') == 'shortcut':
                    continue
                for article in self.articles.get(source['url'], []):
                    articles.setdefault(article['link'], article)
        return sorted(articles.values(), key=lambda a: a['fecha'].timestamp() if a.get('fecha') else 0, reverse=True)

    def article(self, link):
        return next((a for a in self.all_articles() if a['link'] == link), None) or self.library.read('descargas', link) or self.library.read('guardados', link)

    def read(self, article, offline=False):
        article = dict(article)
        link = article['link']
        local = self.library.read('descargas', link)
        if offline:
            if not local:
                raise ValueError('La descarga ya no existe')
            return local
        snapshot = self.reader_store.read(link)
        if snapshot:
            article['cuerpo'] = snapshot['original']
            return article
        if article.get('cuerpo'):
            self.reader_store.save_original(link, article['cuerpo'])
            return article
        if local:
            return local
        if link in self.content:
            return dict(self.content[link])
        text = ''
        try:
            html = core.download(link, timeout=15).decode('utf-8', errors='replace')
            lang = re.search(r'<html\b[^>]*\blang=["\']([a-zA-Z]+)', html, re.I)
            if lang:
                article['idioma_original'] = lang.group(1).lower()
            text = core.article_text(html)
        except Exception:
            pass
        status = 'Texto extraído del sitio'
        if not text:
            parser = core.HtmlContent()
            parser.feed(core.feed_content.get(link, ''))
            text = parser.text()
            status = 'Contenido del feed · Puede ser un resumen'
        if not text:
            raise ValueError('No se pudo recuperar el texto. Puedes abrir el sitio original.')
        article.update(cuerpo=text, estado_contenido=status)
        if not article.get('imagen'):
            article['imagen'] = self.fetch_image(link)
        self.reader_store.save_original(link, text)
        self.content[link] = article
        return article

    def translate(self, text):
        chunks = []
        for paragraph in text.split('\n\n'):
            for part in textwrap.wrap(paragraph, width=1200, break_long_words=False, break_on_hyphens=False):
                result = core.translate_text(part)
                if not result:
                    raise ValueError('No se pudo traducir. Puedes reintentar.')
                chunks.append(result)
        return '\n\n'.join(chunks)

    def translate_article(self, article):
        original = article['cuerpo']
        self.reader_store.save_original(article['link'], original)
        snapshot = self.reader_store.read(article['link'])
        if snapshot and snapshot['translation']:
            return snapshot['translation']
        translated = original if article.get('idioma_original') == 'es' else self.translate(original)
        self.reader_store.save_translation(article['link'], original, translated)
        return translated

    def score(self, article):
        text = article.get('cuerpo') or self.content.get(article['link'], {}).get('cuerpo', '')
        if not text:
            parser = core.HtmlContent()
            parser.feed(core.feed_content.get(article['link'], ''))
            text = parser.text()
        return score_radar(article.get('titulo', '') + ' ' + (article.get('titulo_es') or ''), text,
                            self.config.get('radar_palabras', []))

    def filtered(self, page='feed', category='', source='', query=''):
        articles = self.library.list_items(page) if page in {'guardados', 'descargas'} else self.all_articles()
        if category:
            sources = {s['url'] for c in self.config['categorias'] if c['nombre'] == category for s in c['sitios']}
            articles = [a for a in articles if a.get('source_url') in sources]
        if source:
            articles = [a for a in articles if a.get('source_url') == source]
        if query:
            articles = [a for a in articles if find_matches(a.get('titulo', '') + ' ' + (a.get('titulo_es') or ''), query)]
        if self.config.get('radar_activo'):
            articles.sort(key=self.score, reverse=True)
        return articles
