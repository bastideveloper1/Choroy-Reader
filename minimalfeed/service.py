"""Servicios y estado persistente, independientes de la interfaz gráfica."""
import copy
import hashlib
import io
import json
import os
import tempfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from PIL import Image
from biblioteca import Biblioteca, coincidencias, puntuar_radar
from . import core


class Service:
    def __init__(self, root):
        self.root = Path(root)
        self.config_path = self.root / 'config.json'
        if self.config_path.exists():
            self.config = json.loads(self.config_path.read_text(encoding='utf-8'))
            if not isinstance(self.config.get('categorias'), list):
                raise ValueError('La configuración no contiene una lista de categorías válida')
        else:
            self.config = copy.deepcopy(core.CONFIG_INICIAL)
        self.config.setdefault('color', self.config.get('tema', 'gris'))
        self.config.setdefault('radar_palabras', [])
        self.library = Biblioteca(self.root / 'biblioteca')
        self.articles = {}
        self.content = {}
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
        candidates = [core.urllib.parse.urljoin(link, core.unescape(image_url))] if image_url else []
        for candidate in candidates:
            try:
                data = core.descargar(candidate, timeout=8)
                with Image.open(io.BytesIO(data)) as image:
                    image.verify()
                return data
            except Exception:
                pass
        candidate = core.obtener_imagen_og(link)
        if candidate:
            try:
                data = core.descargar(candidate, timeout=8)
                with Image.open(io.BytesIO(data)) as image:
                    image.verify()
                return data
            except Exception:
                pass
        return None

    def fetch_source(self, source, config):
        source = copy.deepcopy(source)
        feed = source.get('url_feed') or core.descubrir_feed(source['url'])
        source['url_feed'] = feed
        if not feed:
            raise ValueError('No se encontró un feed')
        raw = core.obtener_articulos(feed, maximo=source.get('max_articulos') or core.ARTICULOS_POR_SITIO)
        if raw is None:
            raise ValueError('No se pudo descargar el feed')
        output = []
        for title, link, image, date in raw:
            translate = (config.get('mostrar_titulo_es', True) and source.get('modo_titulo', 'en_es') != 'solo_ingles'
                         and source.get('traduccion_es', True))
            translated = core.traducir_texto(title) if translate else ''
            output.append(dict(titulo=title, titulo_es=translated or '', link=link,
                               imagen=self.fetch_image(link, image), fecha=core.parsear_fecha_texto(date),
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
                    source['ultima_actualizacion'] = core.time.time()
        self.save_config()
        return errors

    def all_articles(self):
        articles = {}
        for category in self.config['categorias']:
            for source in category['sitios']:
                for article in self.articles.get(source['url'], []):
                    articles.setdefault(article['link'], article)
        return sorted(articles.values(), key=lambda a: a['fecha'].timestamp() if a.get('fecha') else 0, reverse=True)

    def article(self, link):
        return next((a for a in self.all_articles() if a['link'] == link), None) or self.library.leer('descargas', link) or self.library.leer('guardados', link)

    def read(self, article, offline=False):
        article = dict(article)
        link = article['link']
        local = self.library.leer('descargas', link)
        if offline:
            if not local:
                raise ValueError('La descarga ya no existe')
            return local
        if article.get('cuerpo'):
            return article
        if local:
            return local
        if link in self.content:
            return dict(self.content[link])
        text = ''
        try:
            html = core.descargar(link, timeout=15).decode('utf-8', errors='replace')
            lang = core.re.search(r'<html\b[^>]*\blang=["\']([a-zA-Z]+)', html, core.re.I)
            if lang:
                article['idioma_original'] = lang.group(1).lower()
            text = core.texto_articulo(html)
        except Exception:
            pass
        status = 'Texto extraído del sitio'
        if not text:
            parser = core.ContenidoHTML()
            parser.feed(core.contenido_feed.get(link, ''))
            text = parser.texto()
            status = 'Contenido del feed · Puede ser un resumen'
        if not text:
            raise ValueError('No se pudo recuperar el texto. Puedes abrir el sitio original.')
        article.update(cuerpo=text, estado_contenido=status)
        if not article.get('imagen'):
            article['imagen'] = self.fetch_image(link)
        self.content[link] = article
        return article

    def translate(self, text):
        chunks = []
        for paragraph in text.split('\n\n'):
            for part in core.textwrap.wrap(paragraph, width=1200, break_long_words=False, break_on_hyphens=False):
                result = core.traducir_texto(part)
                if not result:
                    raise ValueError('No se pudo traducir. Puedes reintentar.')
                chunks.append(result)
        return '\n\n'.join(chunks)

    def score(self, article):
        text = article.get('cuerpo') or self.content.get(article['link'], {}).get('cuerpo', '')
        if not text:
            parser = core.ContenidoHTML()
            parser.feed(core.contenido_feed.get(article['link'], ''))
            text = parser.texto()
        return puntuar_radar(article.get('titulo', '') + ' ' + (article.get('titulo_es') or ''), text,
                            self.config.get('radar_palabras', []))

    def filtered(self, page='feed', category='', source='', query=''):
        articles = self.library.listar(page) if page in {'guardados', 'descargas'} else self.all_articles()
        if category:
            sources = {s['url'] for c in self.config['categorias'] if c['nombre'] == category for s in c['sitios']}
            articles = [a for a in articles if a.get('source_url') in sources]
        if source:
            articles = [a for a in articles if a.get('source_url') == source]
        if query:
            articles = [a for a in articles if coincidencias(a.get('titulo', '') + ' ' + (a.get('titulo_es') or ''), query)]
        if self.config.get('radar_activo'):
            articles.sort(key=self.score, reverse=True)
        return articles
