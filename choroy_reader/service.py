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
from datetime import datetime, timedelta
from PIL import Image
from choroy_reader.library import Library, find_matches, score_radar
from . import core
from .reader_store import ReaderStore
from .lifecycle import Lifecycle


class Service:
    def __init__(self, root, housekeeping=True):
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
        self.config.setdefault('colecciones', [])
        self.library = Library(self.root / 'biblioteca')
        self.articles = {}
        for article in self.library.list_items('feed'):
            self.articles.setdefault(article.get('source_url', ''), []).append(article)
        self.content = {}
        self.reader_store = ReaderStore(self.root / "reader_state.sqlite3")
        self.lifecycle = Lifecycle(self.reader_store)
        self.seen = set(self.config.get('vistos', []))
        self.dismissed = set(self.config.get('descartados', []))
        # Seed history from existing installations without touching saved copies.
        for kind in ('feed', 'guardados', 'descargas', 'archivados'):
            for article in self.library.list_items(kind):
                if not self.library.contains('historial', article['link']):
                    self.remember_article(article)

        if housekeeping:
            self.cleanup_history()

    def cleanup_history(self, now=None):
        now = time.time() if now is None else now
        days = self.config.get('historial_dias', 0)
        removed = 0
        for article in self.library.list_items('historial'):
            link = article['link']
            first_seen, retired = self.lifecycle.remember(link, now)
            protected = link not in self.seen or any(self.library.contains(kind, link) for kind in ('guardados', 'descargas', 'archivados'))
            if days and not protected and now - first_seen >= days * 86400:
                self.library.save('retirados', article)
                self.lifecycle.retire(link, now)
                self.library.delete('historial', link)
                removed += 1
        for article in self.library.list_items('retirados'):
            link = article['link']
            _, retired = self.lifecycle.remember(link, now)
            protected = link not in self.seen or any(self.library.contains(kind, link) for kind in ('guardados', 'descargas', 'archivados'))
            if protected:
                self.restore_history(link, now)
            elif retired is not None and now - retired >= 30 * 86400:
                self.library.delete('retirados', link)
        return removed

    def restore_history(self, link, now=None):
        article = self.library.read('retirados', link)
        if article:
            self.library.save('historial', article)
            self.lifecycle.restore(link, time.time() if now is None else now)
            self.library.delete('retirados', link)

    def save_config(self):
        self.root.mkdir(parents=True, exist_ok=True)
        self.config['vistos'] = sorted(self.seen)
        self.config['descartados'] = sorted(self.dismissed)
        name = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=self.root, delete=False) as f:
                name = f.name
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            os.replace(name, self.config_path)
        finally:
            if name and os.path.exists(name):
                os.unlink(name)

    @staticmethod
    def _size(path):
        """Tamaño real de archivos bajo una ruta, sin seguir enlaces."""
        path = Path(path)
        if not path.exists() or path.is_symlink():
            return 0
        if path.is_file():
            try:
                return path.stat().st_size
            except OSError:
                return 0
        total = 0
        for item in path.rglob('*'):
            try:
                if item.is_file() and not item.is_symlink():
                    total += item.stat().st_size
            except OSError:
                continue
        return total

    def storage_report(self):
        """Desglosa los datos del usuario sin incluir la instalación."""
        database = sum(self._size(self.root / ('reader_state.sqlite3' + suffix))
                       for suffix in ('', '-wal', '-shm'))
        articles = self._size(self.root / 'biblioteca')
        images = self._size(self.root / 'cache' / 'images')
        cache_root = self.root / 'cache'
        cache = max(0, self._size(cache_root) - images)
        total = self._size(self.root)
        accounted = database + articles + images + cache
        return {
            'path': str(self.root), 'database': database, 'articles': articles,
            'images': images, 'cache': cache, 'other': max(0, total - accounted),
            'total': total, 'recoverable': images + cache,
        }

    def clear_regenerable_cache(self):
        """Elimina solo archivos de cache/; no afecta datos de lectura."""
        cache_root = (self.root / 'cache').resolve()
        if not cache_root.exists():
            return 0
        released = 0
        files = sorted(cache_root.rglob('*'), key=lambda item: len(item.parts), reverse=True)
        for item in files:
            try:
                # No seguir enlaces y asegurar que nada salga del directorio cache.
                if item.is_symlink():
                    continue
                resolved = item.resolve()
                if resolved != cache_root and cache_root not in resolved.parents:
                    continue
                if item.is_file():
                    released += item.stat().st_size
                    item.unlink()
                elif item.is_dir():
                    item.rmdir()
            except OSError:
                continue
        return released

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
                # Generar la miniatura mientras se actualiza la fuente evita
                # decodificar imágenes en el hilo de la interfaz al publicar
                # las tarjetas nuevas.
                self.image_url(data)
                return data
            except Exception:
                pass
        candidate = core.get_open_graph_image(link)
        if candidate:
            try:
                data = core.download(candidate, timeout=8)
                with Image.open(io.BytesIO(data)) as image:
                    image.verify()
                self.image_url(data)
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
        raw = core.get_articles(feed, maximum=None)
        if raw is None:
            raise ValueError('No se pudo descargar el feed')
        # Un RSS puede seguir respondiendo aunque no tenga publicaciones dentro
        # del período elegido. Conservamos esa señal para no borrar el último
        # snapshot local durante una actualización normal.
        source['feed_empty_after_period'] = bool(raw)
        output = []
        dated = [(title, link, image, core.parse_date(date)) for title, link, image, date in raw]
        dated = [entry for entry in dated if self.in_period(entry[3], config)]
        dated.sort(key=lambda entry: entry[3].timestamp(), reverse=True)
        unique = {entry[1]: entry for entry in reversed(dated)}
        dated = sorted(unique.values(), key=lambda entry: entry[3].timestamp(), reverse=True)
        for title, link, image, date in dated[:source.get('limite_articulos', 100)]:
            translate = (config.get('mostrar_titulo_es', True) and source.get('modo_titulo', 'en_es') != 'solo_ingles'
                         and source.get('traduccion_es', True))
            translated = core.translate_text(title, skip_spanish=True) if translate else ''
            if translated and ' '.join(translated.casefold().split()) == ' '.join(title.casefold().split()):
                translated = ''
            output.append(dict(titulo=title, titulo_es=translated or '', link=link,
                               imagen=self.fetch_image(link, image), fecha=date,
                               fuente=source['nombre'], source_url=source['url'], traducir_es=translate))
        source['feed_empty_after_period'] = bool(raw) and not bool(output)
        return source, output

    def refresh(self, progress=None, cancel=None):
        config = copy.deepcopy(self.config)
        sources = {s['url']: s for c in config['categorias'] for s in c['sitios']}
        results, updated, errors = {}, {}, []
        def fetch(source):
            if cancel is not None and cancel.is_set():
                return None
            return self.fetch_source(source, config)
        with ThreadPoolExecutor(max_workers=6) as pool:
            tasks = {pool.submit(fetch, s): url for url, s in sources.items()}
            for number, task in enumerate(as_completed(tasks), 1):
                if cancel is not None and cancel.is_set():
                    for pending in tasks:
                        pending.cancel()
                    break
                url = tasks[task]
                try:
                    source, articles = task.result()
                    results[url], updated[url] = articles, source
                except Exception as e:
                    errors.append(f"{sources[url]['nombre']}: {e}")
                if progress:
                    progress(number, len(tasks))
        return results, updated, errors

    def remember_article(self, article):
        # History is metadata, not an offline download or a duplicate image cache.
        _, retired = self.lifecycle.remember(article['link'])
        if retired is None:
            self.library.save('historial', dict(article, cuerpo=None, imagen=None))

    def apply_refresh(self, result):
        articles, updated, errors = result
        for batch in self.articles.values():
            for article in batch:
                if not self.library.contains('historial', article['link']):
                    self.remember_article(article)
        for batch in articles.values():
            for article in batch:
                self.remember_article(article)
        # Una respuesta RSS válida sin entradas para el período no significa que
        # hayan desaparecido los artículos ya descargados. Mantener el snapshot
        # evita que el feed se vacíe al pasar de un día a otro. Un feed realmente
        # vacío (o las llamadas antiguas sin esta señal) sí conserva el
        # comportamiento de reemplazar por una lista vacía.
        for url, batch in articles.items():
            if batch or not updated.get(url, {}).get('feed_empty_after_period'):
                self.articles[url] = batch
        # Each URL has one persistent snapshot, even when several feeds contain it.
        current = {a['link']: a for a in self.all_articles()}
        for article in current.values():
            self.library.save('feed', article)
        for article in self.library.list_items('feed'):
            if article['link'] not in current:
                self.library.delete('feed', article['link'])
        for category in self.config['categorias']:
            for source in category['sitios']:
                if source['url'] in updated:
                    source['url_feed'] = updated[source['url']].get('url_feed')
                    source['sin_feed'] = updated[source['url']].get('sin_feed', False)
                    source['ultima_actualizacion'] = time.time()
        self.save_config()
        self.cleanup_history()
        return errors

    def recover_feed_from_history(self):
        """Recupera el último feed local si sus snapshots se perdieron.

        El historial no se modifica: solo se vuelven a crear las copias de
        feed para fuentes que aún pertenecen a la configuración actual.
        """
        if self.articles:
            return 0
        source_urls = {source['url'] for category in self.config['categorias']
                       for source in category['sitios']
                       if source.get('source_type') != 'shortcut'}
        recovered = [article for article in self.library.list_items('historial')
                     if article.get('source_url') in source_urls
                     and not self.library.contains('archivados', article['link'])]
        for article in recovered:
            self.articles.setdefault(article['source_url'], []).append(article)
            self.library.save('feed', article)
        return len(recovered)

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
        return next((a for a in self.all_articles() if a['link'] == link), None) or self.library.read('descargas', link) or self.library.read('guardados', link) or self.library.read('archivados', link) or self.library.read('historial', link) or self.library.read('retirados', link)

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

    def score(self, article, details=False):
        text = article.get('cuerpo') or self.content.get(article['link'], {}).get('cuerpo', '')
        if not text:
            parser = core.HtmlContent()
            parser.feed(core.feed_content.get(article['link'], ''))
            text = parser.text()
        return score_radar(article.get('titulo', '') + ' ' + (article.get('titulo_es') or ''), text,
                            self.config.get('radar_palabras', []),
                            self.config.get('radar_equivalencias', {}) if self.config.get('radar_bilingue') else None, details=details)

    def in_period(self, date, config=None, now=None):
        if not isinstance(date, datetime):
            return False
        config = self.config if config is None else config
        now = now or datetime.now().astimezone()
        date = date.astimezone()
        period = config.get('periodo_articulos', 'hoy')
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if period == 'dos_dias':
            start -= timedelta(days=1)
        elif period == 'semana':
            start -= timedelta(days=6)
        elif period == 'mes':
            start -= timedelta(days=29)
        elif period == 'ano':
            start = start.replace(month=1, day=1)
        return start <= date <= now

    def filtered(self, page='feed', category='', source='', query=''):
        articles = self.library.list_items(page) if page in {'guardados', 'descargas', 'archivados', 'historial', 'retirados'} else self.all_articles()
        if page == 'feed':
            articles = [a for a in articles if self.in_period(a.get('fecha')) and not self.library.contains('archivados', a['link'])]
        if category:
            sources = {s['url'] for c in self.config['categorias'] if c['nombre'] == category for s in c['sitios']}
            articles = [a for a in articles if a.get('source_url') in sources]
        if source:
            articles = [a for a in articles if a.get('source_url') == source]
        if query:
            articles = [a for a in articles if find_matches(a.get('titulo', '') + ' ' + (a.get('titulo_es') or ''), query)]
        if self.config.get('radar_activo'):
            articles.sort(key=self.score, reverse=True)
        if page == "feed":
            articles.sort(key=lambda article: (article["link"] in self.dismissed, article["link"] in self.seen))
        return articles
