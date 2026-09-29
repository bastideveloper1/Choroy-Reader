"""Puente QObject: las tareas de red nunca modifican la interfaz desde un hilo."""
import uuid
import html
import base64
from functools import lru_cache
import io
import threading
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from PySide6.QtCore import QObject, Signal, Property, Slot, QUrl, QStandardPaths
from PySide6.QtGui import QColor, QTextCursor, QTextCharFormat, QDesktopServices
from PIL import Image
from PIL.PngImagePlugin import PngInfo
from choroy_reader.library import find_matches
from . import core
from .article_model import ArticleModel


@lru_cache(maxsize=64)
def image_ratio(source):
    try:
        with Image.open(io.BytesIO(base64.b64decode(source.split(',', 1)[1]))) as image:
            return image.width / max(1, image.height)
    except (ValueError, IndexError, OSError):
        return 4 / 3


MARKER_COLORS = [
    dict(name='Amarillo', color='#ffe88f'),
    dict(name='Celeste', color='#a8dcff'),
    dict(name='Verde', color='#b7e4b0'),
    dict(name='Rojo pálido', color='#f4aaaa'),
    dict(name='Rosa', color='#f5b8d5'),
]


class Backend(QObject):
    changed = Signal()
    finished = Signal(object)
    progress = Signal(str)
    error = Signal(str)
    document_layout_changed = Signal()
    document_search = Signal(int, int)  # position, count

    def __init__(self, service, asset_dir, parent=None):
        super().__init__(parent)
        self.service = service
        self.asset_dir = Path(asset_dir)
        from .about import load_about
        self.about_info = load_about(self.asset_dir)
        self.notice_title = ''
        self.notice_body = '' 
        self.page, self.category, self.source, self.query = 'feed', '', '', ''
        self.collection_filter = ''
        self.status = 'Listo'
        self.busy = False
        self.active_jobs = 0
        self.portability_busy = False
        self.refresh_cancel = threading.Event()
        self.radar_busy = False
        self.radar_translating = set()
        self.reader = None
        self.reader_font_size = self.service.config.get('tamano_letra_lectura', 16)
        self.reader_body = ''
        self.reader_status = ''
        self.translated = False
        self.translating = False
        self.downloads = set()
        self.bulk_busy = False
        self.read_batch = set()
        self.read_scope = ""
        self.bulk_cancel = threading.Event()
        self._document_key = None
        self.resume_link = None
        self.reader_token = 0
        self.quote_token = 0
        self.quote_data = None
        self.quote_image = None
        self.quote_preview = ''
        self.quote_busy = False
        self.quote_translation = None
        self._document = None
        self.marks = []
        self.find_text = ''
        self.find_index = -1
        self.finished.connect(self._finish)
        self.progress.connect(self._progress)
        self._state = {}
        self.article_model = ArticleModel(self)
        self.storage_info = dict.fromkeys(('data_path', 'installation_path', 'database', 'articles', 'images', 'cache', 'other', 'user_total', 'installation_total', 'recoverable'), 'Calculando…')
        self.storage_info.update(installation_shared=False, recoverable_bytes=0)
        self.publish()

    @staticmethod
    def _format_size(size):
        size = max(0, int(size or 0))
        units = ('B', 'KB', 'MB', 'GB', 'TB')
        for unit in units:
            if size < 1024 or unit == units[-1]:
                return f'{size} {unit}' if unit == 'B' else f'{size:.1f} {unit}'
            size /= 1024

    def _storage_snapshot(self):
        report = self.service.storage_report()
        installation_root = self.asset_dir.parent.resolve()
        data_root = self.service.root.resolve()
        # En una instalación normal ambas rutas son distintas. Si alguien
        # ejecuta el código desde su carpeta de datos, no inventamos un
        # desglose que físicamente no se puede separar.
        shared_location = (data_root == installation_root or
                           data_root in installation_root.parents or
                           installation_root in data_root.parents)
        installation = 0 if shared_location else self.service._size(installation_root)
        return {
            'data_path': report['path'],
            'installation_path': str(installation_root),
            'database': self._format_size(report['database']),
            'articles': self._format_size(report['articles']),
            'images': self._format_size(report['images']),
            'cache': self._format_size(report['cache']),
            'other': self._format_size(report['other']),
            'user_total': self._format_size(report['total']),
            'installation_total': self._format_size(installation) if not shared_location else 'Ubicación compartida',
            'installation_shared': shared_location,
            'recoverable': self._format_size(report['recoverable']),
            'recoverable_bytes': report['recoverable'],
        }

    def background(self, work, callback):
        self.active_jobs += 1
        self.publish()
        def run():
            try:
                result, error = work(), None
            except Exception as e:
                result, error = None, str(e)
            try:
                self.finished.emit((callback, result, error))
            except RuntimeError:
                pass  # The window may have been closed while this worker finished.
        threading.Thread(target=run, daemon=True).start()

    @Slot(object)
    def _finish(self, result):
        callback, value, error = result
        self.active_jobs = max(0, self.active_jobs - 1)
        try:
            callback(value, error)
        except Exception as e:
            self.error.emit(str(e))
        self.publish()

    @Slot(str)
    def _progress(self, value):
        self.status = value
        self._state = dict(self._state, status=value)
        self.changed.emit()

    @Property(QObject, constant=True)
    def articleModel(self):
        return self.article_model

    @Property('QVariantMap', notify=changed)
    def state(self):
        return self._state

    def palette(self):
        name = self.service.config.get('color', 'gris')
        p = core.THEME_PALETTE.get(name, core.THEME_PALETTE['gris'])
        light = name == 'periodico'
        return dict(bg='#e6e6e6' if light else '#111315', panel='#dedede' if light else '#191d23',
                    card='#ededed' if light else '#171717', hover='#cccccc' if light else '#29313d',
                    text='#202020' if light else '#edf1f7', muted='#626262' if light else '#8793a3',
                    border='#b7b7b7' if light else '#30363e', accent=p['base_fuerte'],
                    accent_text='#ffffff' if light else '#171717', light=light)

    def title_html(self, text):
        ranges = find_matches(text, self.query)
        p = self.palette()
        parts, previous = [], 0
        for start, end in ranges:
            parts += [html.escape(text[previous:start]), f'<span style="background-color:{p["accent"]};color:{p["accent_text"]}">{html.escape(text[start:end])}</span>']
            previous = end
        return ''.join(parts) + html.escape(text[previous:])

    def article_view(self, article):
        link = article['link']
        source = next((src for cat in self.service.config['categorias'] for src in cat['sitios']
                       if src['url'] == article.get('source_url')), {})
        translate_enabled = source.get('traduccion_es', True) and source.get('modo_titulo', 'en_es') != 'solo_ingles'
        distinct, count, detected = self.service.score(article, details=True) if self.service.config.get('radar_activo') else (0, 0, [])
        progress = self.service.config.get('progreso_lectura', {}).get(link, {})
        position = progress.get('es' if self.reader and self.reader['link'] == link and self.translated else 'original', {})
        collections = [item['name'] for item in self.service.config.get('colecciones', []) if link in item.get('links', [])]
        return dict(web_extracted=article.get('origen') == 'web', source_url=article.get('source_url', ''), reading_progress=position, link=link, title=article.get('titulo', ''), title_html=self.title_html(article.get('titulo', '')),
                    translation=article.get('titulo_es') or '', translation_html=self.title_html(article.get('titulo_es') or ''),
                    show_translation=bool(self.service.config.get('mostrar_titulo_es', True) and translate_enabled and article.get('traducir_es')), source=article.get('fuente', ''),
                    image=self.service.image_url(article.get('imagen')) or QUrl.fromLocalFile(str(self.asset_dir / 'noimage.png')).toString(),
                    date=('Detectado: ' if article.get('fecha_detectada') else '') + core.relative_date(article.get('fecha')),
                    saved=self.service.library.contains('guardados', link), downloaded=self.service.library.contains('descargas', link),
                    downloading=link in self.downloads, seen=link in self.service.seen,
                    dismissed=link in self.service.dismissed, archived=self.service.library.contains('archivados', link),
                    radar=min(3, distinct), interests=distinct, mentions=count, radar_detected=detected, collections=collections)

    def publish(self):
        cfg = self.service.config
        themes = [dict(key=k, name=v, color=core.THEME_PALETTE[k]['base_fuerte']) for k, v in core.THEME_NAMES.items()]
        categories = []
        for ci, cat in enumerate(cfg['categorias']):
            sources = []
            for si, src in enumerate(cat['sitios']):
                shortcut = src.get('source_type') == 'shortcut'
                show_shortcut = src.get('show_shortcut', shortcut)
                # Un sitio sin RSS ofrecido como atajo se abre directamente.
                direct_access = shortcut or (show_shortcut and bool(src.get('sin_feed')))
                sources.append(dict(category_index=ci, category_name=cat['nombre'], index=si, shortcut=shortcut, show_shortcut=show_shortcut,
                                    direct_access=direct_access,
                                    web=bool(src.get('extraccion_web')), no_feed=bool(src.get('sin_feed')) and not direct_access, name=src['nombre'], url=src['url'], feed=src.get('url_feed') or '',
                                    maximum=src.get('limite_articulos', 100), translate=src.get('modo_titulo', 'en_es') != 'solo_ingles' and src.get('traduccion_es', True),
                                    icon=self.service.favicon_url(src)))
            icon = cat.get('icon') or ''
            if icon and not icon.startswith('file:'):
                icon = QUrl.fromLocalFile(icon).toString()
            categories.append(dict(index=ci, name=cat['nombre'], icon=icon, sources=sources))
        reader = self.article_view(self.reader) if self.reader else {}
        if reader:
            reader.update(notes=self.reader_notes(), font_size=self.reader_font_size, inline_images=self.inline_images(), body=self.reader_body, status=self.reader_status, translated=self.translated,
                          translating=self.translating, ready=bool(self.reader.get('cuerpo')),
                          show_image=cfg.get('mostrar_imagenes_lectura', True))
        collection_items = [dict(id='', name='Todas las colecciones')] + [dict(id=item['id'], name=item['name']) for item in cfg.get('colecciones', [])]
        articles = self.service.filtered(self.page, self.category, self.source, self.query) if self.page in {'feed','guardados','descargas','archivados','historial','retirados'} else []
        if self.page == 'guardados' and self.collection_filter:
            links = next((set(item.get('links', [])) for item in cfg.get('colecciones', []) if item['id'] == self.collection_filter), set())
            articles = [article for article in articles if article['link'] in links]
        self._state = dict(marker_colors=MARKER_COLORS, about=self.about_info, notice_title=self.notice_title, notice_body=self.notice_body, storage=self.storage_info, page=self.page, category=self.category, source=self.source, query=self.query,
                           link_sources=sorted(
                               [src for cat in categories if not self.category or cat['name'] == self.category
                                for src in cat['sources']
                                if src['show_shortcut']
                                and (not self.source or src['url'] == self.source)],
                               key=lambda src: cfg.get('shortcut_order', []).index(src['url']) if src['url'] in cfg.get('shortcut_order', []) else len(cfg.get('shortcut_order', []))),
                           read_batch_count=len(self.read_batch - self.service.seen), read_scope=self.read_scope, read_undo=cfg.get('lectura_deshacer', {}),
                           portability_busy=self.portability_busy, portability_ready=self.active_jobs == 0 and not self.portability_busy, history_days=cfg.get('historial_dias', 0), article_period=cfg.get('periodo_articulos', 'dos_dias'), palette=self.palette(), theme=cfg.get('color', 'gris'), themes=themes, categories=categories,
                           default_font_size=cfg.get('tamano_letra_lectura', 16), columns=cfg.get('articulos_por_fila', 5), show_images=cfg.get('mostrar_imagenes_lectura', True),
                           translate_titles=cfg.get('mostrar_titulo_es', True), radar=cfg.get('radar_activo', False),
                           radar_words=list(cfg.get('radar_palabras', [])), radar_busy=self.radar_busy,
                           radar_bilingual=bool(cfg.get('radar_bilingue')),
                           radar_equivalents=cfg.get('radar_equivalencias', {}),
                           radar_translating=bool(self.radar_translating),
                           total_articles=len(self.service.all_articles()), bulk_busy=self.bulk_busy, bulk_cancelling=self.bulk_busy and self.bulk_cancel.is_set(), busy=self.busy, refresh_cancelling=self.busy and self.refresh_cancel.is_set(), status=self.status, reader=reader,
                           collections=collection_items, collection_filter=self.collection_filter,
                           articles=[self.article_view(a) for a in articles],
                           logo=QUrl.fromLocalFile(str(self.asset_dir / 'choroy_reader_logo.png')).toString(),
                           quote_backgrounds=core.QUOTE_BACKGROUNDS, quote_preview=self.quote_preview, quote_busy=self.quote_busy,
                           quote_can_save=self.quote_image is not None and not self.quote_busy,
                           quote_has_image=bool(self.quote_data and self.quote_data['article'].get('imagen')),
                           quote_is_translated=bool(self.quote_data and self.quote_data['translated']),
                           quote_has_original=bool(self.quote_data and self.quote_data.get('original_text')),
                           quote_original_body=self.quote_data['article'].get('cuerpo', '') if self.quote_data else '',
                           quote_title_has_translation=bool(self.quote_data and self.quote_data['article'].get('titulo_es')),
                           downloads_folder=QUrl.fromLocalFile(QStandardPaths.writableLocation(QStandardPaths.DownloadLocation)).toString())
        self.article_model.update(self._state['articles'])
        self.changed.emit()

    def startup(self, allow_network=True):
        cached = bool(self.service.articles)
        if cached:
            self.status = 'Feed guardado · Pulsa Actualizar feed para buscar novedades'
            self.publish()
        def done(value, error):
            if error:
                self.error.emit(error)
            if allow_network and not cached:
                self.refresh()
        self.background(self.service.initialize_history, done)

    @Slot()
    def refresh(self):
        if self.busy:
            return
        self.refresh_cancel.clear()
        self.busy, self.status = True, 'Actualizando…'
        self.publish()
        def done(value, error):
            self.busy = False
            if self.refresh_cancel.is_set():
                self.status = 'Actualización cancelada · Se conserva el feed anterior'
            elif error:
                self.status = 'Error al actualizar'
                self.error.emit(error)
            else:
                errors = self.service.apply_refresh(value)
                self.status = 'Última actualización: ' + datetime.now().strftime('%H:%M')
                if errors:
                    self.status += f' · {len(errors)} fuentes sin respuesta'
            self.publish()
            if not error and not self.refresh_cancel.is_set():
                self.analyze_radar()
        self.background(lambda: self.service.refresh(lambda n,t: self.progress.emit(f'Cargando fuentes: {n}/{t}'), self.refresh_cancel), done)

    @Slot()
    def cancel_refresh(self):
        if self.busy:
            self.refresh_cancel.set()
            self.status = 'Cancelando actualización…'
            self.publish()

    @Slot(str, str, str)
    def navigate(self, page, category='', source=''):
        self.reader_token += 1
        self.page, self.category, self.source = page, category, source
        self.reader = None
        self.reader_body = ''
        self.publish()
        if page == 'storage':
            self.refresh_storage()

    @Slot()
    def refresh_storage(self):
        def done(value, error):
            if error:
                self.error.emit(error)
            else:
                self.storage_info = value
            self.publish()
        self.background(self._storage_snapshot, done)

    @Slot()
    def clear_storage_cache(self):
        def work():
            released = self.service.clear_regenerable_cache()
            return released, self._storage_snapshot()

        def done(value, error):
            if error:
                self.error.emit(error)
            else:
                released, self.storage_info = value
                self.status = 'Caché limpiada · ' + self._format_size(released) + ' recuperados'
            self.publish()
        self.background(work, done)

    @Slot(str)
    def search_titles(self, query):
        self.query = query.strip()
        self.publish()

    @Slot(str)
    def set_theme(self, theme):
        if theme in core.THEME_PALETTE:
            self.service.config.update(color=theme, tema=theme)
            self.service.save_config()
            self.publish()
            self.render_document()

    def inline_images(self):
        if not self.reader or not self.service.config.get('mostrar_imagenes_lectura', True):
            return []
        paragraphs = self.reader_body.split('\n\n')
        images = []
        for entry in self.reader.get('imagenes_cuerpo') or []:
            index = min(entry['paragraph'], len(paragraphs) - 1)
            prefix = '\n\n'.join(paragraphs[:index + 1])
            position = len(prefix.encode('utf-16-le')) // 2
            stack = sum(1 for image in images if image['position'] == position)
            if entry.get('source'):
                images.append(dict(source=entry['source'], alt=entry.get('alt', ''), position=position, stack=stack))
        return images

    @Slot(int, bool)
    def set_reader_font_size(self, size, default=False):
        if size not in (14, 16, 20, 24):
            return
        self.reader_font_size = size
        if default:
            self.service.config['tamano_letra_lectura'] = size
            self.service.save_config()
        self.publish()

    @Slot(int, bool, bool)
    def set_design(self, columns, images, translations):
        self.service.config.update(articulos_por_fila=max(1,min(5,columns)), mostrar_imagenes_lectura=images,
                                   mostrar_titulo_es=translations)
        self.service.save_config()
        self.publish()
        self.render_document()

    @Slot()
    def toggle_radar(self):
        self.service.config['radar_activo'] = not self.service.config.get('radar_activo', False)
        self.service.save_config()
        self.publish()
        self.analyze_radar()

    @Slot(str)
    def save_radar(self, words):
        self.service.config['radar_palabras'] = list(dict.fromkeys(p.strip() for p in words.split(',') if p.strip()))
        self.service.save_config()
        self.publish()
        self.analyze_radar()

    @Slot(str)
    def add_radar_word(self, word):
        word = ' '.join(word.split())
        words = self.service.config.get('radar_palabras', [])
        if not word or any(w.casefold() == word.casefold() for w in words):
            return
        self.service.config['radar_palabras'] = [*words, word]
        if self.service.config.get('radar_bilingue'):
            self.suggest_radar_equivalents(word)
        self.service.save_config()
        self.publish()
        self.analyze_radar()

    @Slot(bool)
    def set_radar_bilingual(self, enabled):
        self.service.config['radar_bilingue'] = enabled
        self.service.save_config()
        if enabled:
            for word in self.service.config.get('radar_palabras', []):
                if word not in self.service.config.get('radar_equivalencias', {}):
                    self.suggest_radar_equivalents(word)
        self.publish()

    @Slot(str, str)
    def save_radar_equivalents(self, word, text):
        if word not in self.service.config.get('radar_palabras', []):
            return
        self.service.config.setdefault('radar_equivalencias', {})[word] = list(
            dict.fromkeys(p.strip() for p in text.split(',') if p.strip()))
        self.service.save_config()
        self.publish()

    @Slot(str)
    def suggest_radar_equivalents(self, word):
        if word in self.radar_translating:
            return
        self.radar_translating.add(word)
        previous = self.service.config.get('radar_equivalencias', {}).get(word)
        self.publish()
        def work():
            results = [core.translate_text(word, target_language=lang) for lang in ('es', 'en')]
            if not all(results):
                raise ValueError('No se pudieron obtener equivalencias. Puedes escribirlas o reintentar.')
            return list(dict.fromkeys(p for p in results if p.casefold() != word.casefold()))
        def done(value, error):
            self.radar_translating.discard(word)
            if word in self.service.config.get('radar_palabras', []):
                if error:
                    self.error.emit(str(error))
                else:
                    equivalents = self.service.config.setdefault('radar_equivalencias', {})
                    if equivalents.get(word) == previous:
                        equivalents[word] = value
                        self.service.save_config()
            self.publish()
        self.background(work, done)

    @Slot(str)
    def remove_radar_word(self, word):
        self.service.config['radar_palabras'] = [w for w in self.service.config.get('radar_palabras', []) if w != word]
        self.service.save_config()
        self.publish()
        self.analyze_radar()

    @Slot()
    def analyze_radar(self):
        if self.radar_busy or not self.service.config.get('radar_activo') or not self.service.config.get('radar_palabras'):
            return
        self.radar_busy = True
        articles = list(self.service.all_articles())
        def work():
            def read(a):
                try:
                    self.service.read(a)
                except Exception:
                    pass
            with ThreadPoolExecutor(max_workers=4) as pool:
                list(pool.map(read, articles))
        def done(value, error):
            self.radar_busy = False
            self.publish()
        self.background(work, done)

    @Slot(str)
    def open_article_at_position(self, link):
        self.open_article(link)
        self.resume_link = link

    @Slot(str)
    def open_article(self, link):
        self.resume_link = None
        article = self.service.article(link)
        if not article:
            return
        offline = self.page == 'descargas'
        self.reader_token += 1
        token = self.reader_token
        self.reader_font_size = self.service.config.get('tamano_letra_lectura', 16)
        self.reader, self.reader_body, self.reader_status = dict(article), '', 'Cargando artículo…'
        self.translated, self.translating = False, False
        self.publish()
        def done(value, error):
            if token != self.reader_token:
                return
            if error:
                self.reader_status = error
            else:
                self.reader = value
                self.reader_body = value['cuerpo']
                self.reader_status = value.get('estado_contenido', '')
            self.publish()
        self.background(lambda: self.service.read(article, offline), done)

    @Slot()
    def close_article(self):
        self.reader_token += 1
        self.reader = None
        self.reader_body = ''
        self.publish()

    @Slot()
    def translate_article(self):
        if not self.reader or not self.reader.get('cuerpo') or self.translating:
            return
        if self.translated:
            self.clear_document_format()
            self.translated = False
            self.reader_body = self.reader['cuerpo']
            self.reader_status = self.reader.get('estado_contenido', '')
            self.publish()
            return
        token, link = self.reader_token, self.reader['link']
        def done(value, error):
            if token != self.reader_token:
                return
            self.translating = False
            if error:
                self.error.emit(error)
            else:
                self.clear_document_format()
                self.reader_body, self.translated = value, True
                self.reader_status = 'Versión en español · Traducción automática'
            self.publish()
        snapshot = self.service.reader_store.read(link)
        if snapshot and snapshot['translation']:
            done(snapshot['translation'], None)
        else:
            self.translating = True
            self.publish()
            self.background(lambda article=dict(self.reader): self.service.translate_article(article), done)

    def get_article(self, link):
        return self.reader if self.reader and self.reader['link'] == link else self.service.article(link)

    @Slot(int)
    def show_dependency_license(self, index):
        if not 0 <= index < len(self.about_info['dependencies']):
            return
        from .about import notice_text
        dependency = self.about_info['dependencies'][index]
        try:
            self.notice_body = notice_text(self.asset_dir, dependency)
            self.notice_title = dependency['name'] + ' · ' + dependency['version']
            self.publish()
        except Exception as error:
            self.error.emit(str(error))

    @Slot(str, str)
    def portability_action(self, action, url):
        if self.active_jobs or self.portability_busy:
            self.error.emit('Espera a que terminen las tareas en curso antes de importar o respaldar.')
            return
        from . import portability
        path = QUrl(url).toLocalFile()
        if not path or action not in {'import_opml', 'export_opml', 'backup', 'restore'}:
            self.error.emit('Selecciona un archivo local válido')
            return
        self.portability_busy = True
        self.status = 'Procesando archivo local…'
        self.publish()
        def work():
            if action == 'backup':
                portability.create_backup(self.service, path)
                return None
            if action == 'restore':
                return portability.restore_backup(self.service, path)
            if action == 'export_opml':
                portability.export_opml(self.service.config, portability.safe_target(self.service.root, path))
                return None
            return portability.import_opml(self.service.config, path)
        def done(value, error):
            self.portability_busy = False
            if error:
                self.status = 'No se pudo completar la operación'
                self.error.emit(error)
            elif action == 'restore':
                self.service, recovery = value
                self.reader_token += 1
                self.reader = None
                self.reader_body = ''
                self._document = None
                self._document_key = None
                self.marks = []
                self.read_batch.clear()
                self.page, self.category, self.source, self.query = 'sources', '', '', ''
                self.status = 'Copia restaurada · Respaldo anterior: ' + str(recovery)
            elif action == 'import_opml':
                config, added, skipped = value
                previous = self.service.config
                self.service.config = config
                try:
                    self.service.save_config()
                except Exception:
                    self.service.config = previous
                    raise
                self.status = f'OPML importado · {added} fuentes añadidas · {skipped} omitidas · Actualiza el feed'
            else:
                self.status = 'Archivo guardado: ' + path
            self.publish()
        self.background(work, done)

    @Slot(int)
    def set_history_retention(self, days):
        if days not in {0, 1, 7, 30, 90, 180, 365}:
            return
        self.service.config['historial_dias'] = days
        self.service.save_config()
        self.service.cleanup_history()
        self.publish()

    @Slot(str)
    def restore_history(self, link):
        self.service.restore_history(link)
        self.publish()

    @Slot(str)
    def set_article_period(self, period):
        if period not in {'hoy', 'dos_dias', 'semana', 'mes', 'ano'}:
            return
        self.service.config['periodo_articulos'] = period
        self.service.save_config()
        self.status = 'Período guardado · Actualiza el feed para buscar artículos de ese período'
        self.publish()

    @Slot(str)
    def prepare_mark_all_read(self, scope):
        if scope not in {'source', 'category', 'library'}:
            return
        entries = [a for values in self.service.articles.values() for a in values]
        for kind in ('guardados', 'descargas', 'archivados', 'historial'):
            entries.extend(self.service.library.list_items(kind))
        if scope == 'source':
            entries = [a for a in entries if self.source and a.get('source_url') == self.source]
            name = next((src['nombre'] for cat in self.service.config['categorias'] for src in cat['sitios'] if src['url'] == self.source), self.source)
            self.read_scope = 'Fuente: ' + name
        elif scope == 'category':
            urls = {src['url'] for cat in self.service.config['categorias'] if cat['nombre'] == self.category for src in cat['sitios']}
            entries = [a for a in entries if a.get('source_url') in urls]
            self.read_scope = 'Categoría: ' + self.category
        else:
            self.read_scope = 'Biblioteca completa'
        self.read_batch = {a['link'] for a in entries} - self.service.seen
        self.publish()

    @Slot()
    def mark_all_read(self):
        changed = self.read_batch - self.service.seen
        if not changed:
            return
        self.service.seen.update(changed)
        self.service.config['lectura_deshacer'] = dict(links=sorted(changed), scope=self.read_scope, count=len(changed))
        self.read_batch.clear()
        self.service.save_config()
        self.publish()

    @Slot()
    def undo_mark_all_read(self):
        undo = self.service.config.pop('lectura_deshacer', {})
        self.service.seen.difference_update(undo.get('links', []))
        self.service.save_config()
        self.publish()

    @Slot(str)
    def toggle_read(self, link):
        if not self.get_article(link):
            return
        undo = self.service.config.get('lectura_deshacer', {})
        if link in undo.get('links', []):
            undo['links'].remove(link)
        if link in self.service.seen:
            self.service.seen.remove(link)
        else:
            self.service.seen.add(link)
        self.service.save_config()
        self.publish()

    @Slot(str)
    def toggle_dismissed(self, link):
        if not self.get_article(link):
            return
        if link in self.service.dismissed:
            self.service.dismissed.remove(link)
        else:
            self.service.dismissed.add(link)
        self.service.save_config()
        if link in self.service.dismissed and self.reader and self.reader['link'] == link:
            self.close_article()
        else:
            self.publish()

    @Slot(str)
    def toggle_archived(self, link):
        article = self.get_article(link)
        if not article:
            return
        try:
            if self.service.library.contains('archivados', link):
                # Restore even when the article has dropped out of the latest RSS.
                source = article.get('source_url', '')
                if not any(a['link'] == link for a in self.service.articles.get(source, [])):
                    self.service.articles.setdefault(source, []).append(dict(article))
                self.service.library.save('feed', article)
                self.service.library.delete('archivados', link)
            else:
                self.service.library.save('archivados', article)
            self.publish()
        except Exception as error:
            self.error.emit(str(error))

    @Slot(str)
    def toggle_saved(self, link):
        article = self.get_article(link)
        if not article:
            return
        try:
            if self.service.library.contains('guardados', link):
                self.service.library.delete('guardados', link)
                for collection in self.service.config.get('colecciones', []):
                    collection['links'] = [item for item in collection.get('links', []) if item != link]
                self.service.save_config()
            else:
                self.service.library.save('guardados', article)
            self.publish()
        except Exception as e:
            self.error.emit(str(e))

    @Slot(str)
    def set_collection_filter(self, collection_id):
        self.collection_filter = collection_id if any(item['id'] == collection_id for item in self.service.config.get('colecciones', [])) else ''
        self.publish()

    @Slot(str)
    def save_collection(self, name):
        name = name.strip()
        if not name:
            self.error.emit('Escribe un nombre para la colección')
            return
        if any(item['name'].casefold() == name.casefold() for item in self.service.config.get('colecciones', [])):
            self.error.emit('Ya existe una colección con ese nombre')
            return
        import uuid
        self.service.config.setdefault('colecciones', []).append({'id': uuid.uuid4().hex, 'name': name, 'links': []})
        self.service.save_config()
        self.publish()

    @Slot(str)
    def delete_collection(self, collection_id):
        self.service.config['colecciones'] = [item for item in self.service.config.get('colecciones', []) if item['id'] != collection_id]
        if self.collection_filter == collection_id:
            self.collection_filter = ''
        self.service.save_config()
        self.publish()

    @Slot(str, str)
    def toggle_article_collection(self, link, collection_id):
        if not self.service.library.contains('guardados', link):
            self.error.emit('Guarda el artículo antes de organizarlo en colecciones')
            return
        collection = next((item for item in self.service.config.get('colecciones', []) if item['id'] == collection_id), None)
        if not collection:
            return
        links = collection.setdefault('links', [])
        if link in links:
            links.remove(link)
        else:
            links.append(link)
        self.service.save_config()
        self.publish()

    @Slot(str)
    def toggle_download(self, link):
        if link in self.downloads:
            return
        article = self.get_article(link)
        if not article:
            return
        if self.service.library.contains('descargas', link):
            try:
                self.service.library.delete('descargas', link)
                self.publish()
            except Exception as e:
                self.error.emit(str(e))
            return
        self.downloads.add(link)
        self.publish()
        def work():
            result = self.service.read(article)
            self.service.library.save('descargas', result)
        def done(value, error):
            self.downloads.discard(link)
            if error:
                self.error.emit(error)
            else:
                self.status = 'Artículo disponible sin conexión'
            self.publish()
        self.background(work, done)

    @Slot(str)
    def open_url(self, url):
        if QUrl(url).scheme() in {'https', 'http'}:
            QDesktopServices.openUrl(QUrl(url))

    @Slot(int, str)
    @Slot(int, str, str)
    def save_category(self, index, name, icon=None):
        name = name.strip()
        cats = self.service.config['categorias']
        if not name or any(c['nombre'] == name and i != index for i,c in enumerate(cats)):
            self.error.emit('El nombre está vacío o ya existe')
            return
        if index < 0:
            cats.append(dict(nombre=name, sitios=[]))
        elif index < len(cats):
            old_name = cats[index]['nombre']
            cats[index]['nombre'] = name
            if self.category == old_name:
                self.category = name
        else:
            return
        if icon is not None:
            cats[-1 if index < 0 else index]['icon'] = QUrl(icon).toLocalFile() if icon.startswith('file:') else icon
        self.service.save_config()
        self.publish()

    @Slot(int)
    def delete_category(self, index):
        cats = self.service.config['categorias']
        if 0 <= index < len(cats):
            if cats[index]['sitios']:
                self.error.emit('Mueve o elimina las fuentes antes de borrar la categoría')
                return
            cats.pop(index)
            self.service.save_config()
            self.publish()

    @Slot(int, int)
    def move_category(self, index, delta):
        cats = self.service.config['categorias']
        if 0 <= index < len(cats) and 0 <= index+delta < len(cats):
            cats.insert(index+delta, cats.pop(index))
            self.service.save_config()
            self.publish()

    @Slot(int, int, str)
    def set_source_shortcut(self, category, index, mode):
        cats = self.service.config['categorias']
        if mode not in {'remove', 'only', 'add'} or not 0 <= category < len(cats):
            return
        if not 0 <= index < len(cats[category]['sitios']):
            return
        source = cats[category]['sitios'][index]
        source['show_shortcut'] = mode != 'remove'
        if mode != 'remove':
            source['source_type'] = 'shortcut' if mode == 'only' else 'feed'
        self.service.save_config()
        self.publish()

    @Slot(str, str)
    def move_shortcut(self, url, target):
        order = list(dict.fromkeys(src['url'] for src in sorted(
            [src for cat in self.service.config['categorias'] for src in cat['sitios']],
            key=lambda src: self.service.config.get('shortcut_order', []).index(src['url'])
            if src['url'] in self.service.config.get('shortcut_order', [])
            else len(self.service.config.get('shortcut_order', [])))))
        if url not in order or target not in order or url == target:
            return
        destination = order.index(target)
        order.remove(url)
        order.insert(destination, url)
        self.service.config['shortcut_order'] = order
        self.service.save_config()
        self.publish()

    @Slot(int, int, int, str, str, str, int, bool, str, bool, result=bool)
    @Slot(int, int, int, str, str, str, int, bool, str, bool, bool, result=bool)
    def save_source(self, category, index, destination, name, url, feed, maximum, translate, icon, shortcut=False, show_shortcut=None):
        cats = self.service.config['categorias']
        if not (0 <= destination < len(cats)) or not name.strip() or not url.strip():
            self.error.emit('Completa nombre, dirección y categoría')
            return False
        url = url.strip()
        if '://' not in url:
            url = 'https://' + url
        if QUrl(url).scheme() not in {'http','https'} or (feed and QUrl(feed).scheme() not in {'http','https'}):
            self.error.emit('La dirección debe comenzar con http:// o https://')
            return False
        source = core.source_defaults(name.strip(), url)
        position = len(cats[destination]['sitios'])
        if index >= 0 and 0 <= category < len(cats) and index < len(cats[category]['sitios']):
            source = cats[category]['sitios'][index].copy()
            if destination == category:
                position = index
            cats[category]['sitios'].pop(index)
        if any(entry['url'].rstrip('/') == url.rstrip('/') for i, entry in enumerate(cats[destination]['sitios'])):
            self.error.emit('Esta página ya está en la categoría. Edita la entrada existente para cambiar su tipo.')
            # Restore an edited entry if destination validation failed.
            if index >= 0:
                cats[category]['sitios'].insert(index, source)
            return False
        source.pop('sin_feed', None)
        source.pop('extraccion_web', None)
        source['source_type'] = 'shortcut' if shortcut else 'feed'
        source['show_shortcut'] = shortcut if show_shortcut is None else show_shortcut
        source.update(nombre=name.strip(), url=url, url_feed=feed.strip() or None, limite_articulos=max(1,min(1000,maximum)),
                      modo_titulo='en_es' if translate else 'solo_ingles', traduccion_es=translate,
                      favicon_personalizado=QUrl(icon).toLocalFile() if icon.startswith('file:') else icon or None)
        cats[destination]['sitios'].insert(position, source)
        self.service.save_config()
        self.status = 'Fuente guardada · Pulsa Actualizar feed para cargarla'
        self.publish()
        if shortcut:
            self.status = 'Atajo web guardado'
            self.publish()
            self.background(lambda: self.service.fetch_favicon(source), lambda value, error: self.publish())
        elif not source['url_feed']:
            def discover():
                self.service.fetch_favicon(source)
                found = core.discover_feed(url)
                if not found:
                    core.download(url, timeout=10)
                return found
            def discovered(found, error):
                if not any(source is entry for cat in cats for entry in cat['sitios']):
                    return False
                if not error:
                    source['url_feed'] = found
                    source['sin_feed'] = False
                    source['extraccion_web'] = not bool(found)
                    self.service.save_config()
                self.status = ('No se pudo comprobar el feed · Reintenta con Actualizar feed' if error else
                               'Fuente web sin RSS · Pulsa Actualizar feed para extraer publicaciones' if not found else
                               'Feed encontrado · Pulsa Actualizar feed para cargar artículos')
                self.publish()
            self.background(discover, discovered)
        return True

    @Slot(int, int)
    def delete_source(self, category, index):
        cats = self.service.config['categorias']
        if 0 <= category < len(cats) and 0 <= index < len(cats[category]['sitios']):
            cats[category]['sitios'].pop(index)
            self.service.save_config()
            self.publish()

    @Slot(int, int, int)
    def move_source(self, category, index, delta):
        sources = self.service.config['categorias'][category]['sitios']
        if 0 <= index+delta < len(sources):
            sources.insert(index+delta, sources.pop(index))
            self.service.save_config()
            self.publish()

    @Slot(str)
    def prepare_quote(self, text):
        if not self.reader or not text.strip() or len(text.strip()) > 500:
            self.error.emit('Selecciona un fragmento de hasta 500 caracteres')
            return
        self.quote_token += 1
        self.quote_busy = False
        self.quote_data = dict(text=text.strip(), article=dict(self.reader), translated=self.translated,
                               original_text='' if self.translated else text.strip())
        self.quote_translation = text.strip() if self.translated else None
        self.quote_image = None
        self.quote_preview = ''
        self.publish()

    @Slot(str, result=bool)
    def set_quote_original(self, text):
        text = text.replace('\u2029', '\n').strip()
        if not self.quote_data or not text or len(text) > 500:
            return False
        if text not in self.quote_data['article'].get('cuerpo', ''):
            self.error.emit('Selecciona un fragmento del texto original.')
            return False
        self.quote_data['original_text'] = text
        self.publish()
        return True

    @Slot(bool, bool, str)
    @Slot(bool, bool, bool, str)
    @Slot(bool, bool, bool, str, str)
    def update_quote(self, spanish, image, title_spanish=False, theme=None, background=""):
        # Conserva compatibilidad con la llamada anterior de tres argumentos.
        if theme is None and isinstance(title_spanish, str):
            theme, title_spanish = title_spanish, False
        theme = theme or self.service.config.get('color', 'gris')
        if not self.quote_data:
            return
        if not spanish and not self.quote_data.get('original_text'):
            self.error.emit('Selecciona el fragmento en el original para conservar sus palabras exactas')
            return
        self.quote_token += 1
        token, data = self.quote_token, dict(self.quote_data)
        self.quote_busy = True
        self.quote_image = None
        cached_translation = self.quote_translation
        self.publish()
        def work():
            text = data['text'] if spanish else data['original_text']
            translated_text = cached_translation
            if spanish:
                translated_text = translated_text or self.service.translate(text)
                text = translated_text
            a = data['article']
            title = a.get('titulo_es') if title_spanish and a.get('titulo_es') else a.get('titulo', '')
            img = core.create_quote_image(text, a.get('fuente',''), a['link'], spanish,
                    title=title, color=core.THEME_PALETTE[theme]['base_fuerte'],
                    image_bytes=a.get('imagen') if image else None, original_language=a.get('idioma_original',''), theme=theme, background=background)
            return img, translated_text
        def done(value, error):
            if token != self.quote_token:
                return
            self.quote_busy = False
            if error:
                self.error.emit(error)
            else:
                self.quote_image, self.quote_translation = value
                out = io.BytesIO()
                # La vista previa puede ser más liviana; el archivo exportado
                # conserva la imagen maestra de 2160 px sin reescalarla.
                preview = self.quote_image.copy()
                preview.thumbnail((1080, 1080), Image.Resampling.LANCZOS)
                preview.save(out, 'PNG')
                self.quote_preview = self.service.image_url(out.getvalue())
            self.publish()
        # La cita original no requiere red: producirla de inmediato evita una
        # vista previa innecesariamente tardía. Las traducciones siguen fuera
        # del hilo de interfaz porque pueden solicitar red.
        if not spanish:
            try:
                done(work(), None)
            except Exception as error:
                done(None, str(error))
        else:
            self.background(work, done)

    @Slot(str)
    def export_quote(self, url):
        if self.quote_image is None or not self.quote_data:
            return
        path = QUrl(url).toLocalFile()
        if not path:
            return
        try:
            if Path(path).suffix.lower() in {'.jpg','.jpeg'}:
                self.quote_image.convert('RGB').save(path, 'JPEG', quality=98, subsampling=0, optimize=True)
            else:
                if not Path(path).suffix:
                    path += '.png'
                metadata = PngInfo()
                metadata.add_text('Fuente', self.quote_data['article']['link'])
                self.quote_image.save(path, 'PNG', pnginfo=metadata)
            self.status = 'Imagen guardada'
            self.publish()
        except Exception as e:
            self.error.emit(str(e))

    def clear_document_format(self):
        self.marks = []
        self.find_text = ''
        self.render_document()
        self._document_key = None

    @Slot()
    def cancel_download_all(self):
        if self.bulk_busy:
            self.bulk_cancel.set()
            self.status = 'Cancelando descargas…'
            self.publish()

    @Slot(bool)
    def download_all(self, include_translation):
        if self.bulk_busy:
            return
        articles = [dict(article) for article in self.service.all_articles() if article['link'] not in self.downloads]
        if not articles:
            return
        self.bulk_cancel.clear()
        self.bulk_busy = True
        links = {article['link'] for article in articles}
        created = set()
        self.downloads.update(links)
        self.publish()
        def work():
            errors = []
            downloaded = 0
            for index, article in enumerate(articles, 1):
                if self.bulk_cancel.is_set():
                    break
                try:
                    existing = self.service.library.read('descargas', article['link'])
                    result = existing or self.service.read(article)
                    if self.bulk_cancel.is_set():
                        break
                    if include_translation:
                        self.service.translate_article(result)
                    if self.bulk_cancel.is_set():
                        break
                    if not existing:
                        self.service.library.save('descargas', result)
                        created.add(article['link'])
                    downloaded += 1
                except Exception as error:
                    errors.append(article.get('titulo', article['link']) + ': ' + str(error))
                if not self.bulk_cancel.is_set():
                    self.progress.emit(f'Preparando lectura sin conexión: {index}/{len(articles)}')
            return downloaded, errors
        def done(result, error):
            cancelled = self.bulk_cancel.is_set()
            cleanup_errors = []
            if cancelled:
                for link in created:
                    try:
                        self.service.library.delete('descargas', link)
                    except Exception as cleanup_error:
                        cleanup_errors.append(str(cleanup_error))
            self.bulk_busy = False
            self.downloads.difference_update(links)
            if cancelled:
                self.status = ('Descarga cancelada · No se pudieron eliminar algunas descargas nuevas' if cleanup_errors else
                               'Descarga cancelada · Se eliminaron las descargas nuevas')
                if cleanup_errors:
                    self.error.emit('\n'.join(cleanup_errors))
            elif error:
                self.error.emit(error)
            else:
                count, errors = result
                self.status = f'{count} artículos disponibles sin conexión'
                if errors:
                    self.error.emit('Algunas descargas o traducciones fallaron:\n' + '\n'.join(errors))
            self.publish()
        self.background(work, done)

    @Slot(int)
    def save_reading_position(self, position):
        if not self.reader or not self.reader_body or not self._document:
            return
        length = self._document.characterCount() - 1
        if length <= 0:
            return
        position = max(0, min(position, length))
        language = 'es' if self.translated else 'original'
        entry = dict(position=position, percent=round(position * 100 / length), length=length)
        self.service.config.setdefault('progreso_lectura', {}).setdefault(self.reader['link'], {})[language] = entry
        self.service.save_config()
        self.publish()

    @Slot()
    def resume_reading(self):
        if not self.reader or not self._document:
            return
        language = 'es' if self.translated else 'original'
        entry = self.service.config.get('progreso_lectura', {}).get(self.reader['link'], {}).get(language)
        if entry:
            self.document_search.emit(min(entry['position'], self._document.characterCount() - 1), 0)

    @Slot(QObject)
    def attach_document(self, quick_document):
        # Keep the Qt Quick wrapper alive alongside its document.
        self._quick_document = quick_document
        document = quick_document.textDocument() if hasattr(quick_document, 'textDocument') else quick_document
        if self._document is not document:
            if self._document is not None:
                try:
                    layout = self._document.documentLayout()
                    layout.documentSizeChanged.disconnect(self._notify_document_layout)
                    layout.update.disconnect(self._notify_document_layout)
                except (RuntimeError, TypeError):
                    pass
            layout = document.documentLayout()
            layout.documentSizeChanged.connect(self._notify_document_layout)
            layout.update.connect(self._notify_document_layout)
        self._document = document
        self.marks, self.find_text, self.find_index = [], '', -1
        self._document_key = None
        if self.reader and self.reader_body:
            language = 'es' if self.translated else 'original'
            self._document_key = (self.reader['link'], language, self.reader_body)
            self.service.reader_store.save_original(self.reader['link'], self.reader['cuerpo'])
            snapshot = self.service.reader_store.read(self.reader['link'])
            self.marks = self.normalize_marks(snapshot['translated_marks' if self.translated else 'original_marks'])
        self.render_document()
        if self.reader and self.reader_body and self.resume_link == self.reader['link']:
            self.resume_link = None
            self.resume_reading()

    def reader_notes(self):
        if not self.reader or not self.reader_body:
            return []
        return self.service.reader_store.read_notes(
            self.reader['link'], 'es' if self.translated else 'original', self.reader_body)

    @Slot(int, result='QVariantMap')
    def create_note(self, position):
        if not self._document_key or not self.reader:
            return {}
        link, language, body = self._document_key
        if (link, language, body) != (self.reader['link'], 'es' if self.translated else 'original', self.reader_body):
            return {}
        note = dict(id=uuid.uuid4().hex, position=max(0, min(position, self.document_length())),
                    text='', color=MARKER_COLORS[0]['color'], images=[], theme='periodico')
        try:
            if not self.service.library.contains('guardados', link):
                self.service.library.save('guardados', self.reader)
            self.service.reader_store.save_note(link, language, body, note)
            self.publish()
            return note
        except Exception as error:
            self.error.emit('No se pudo crear la nota: ' + str(error))
            return {}

    @Slot(str, str, str, 'QVariantList', result=bool)
    def save_note(self, note_id, text, color, images):
        note = next((item for item in self.reader_notes() if item['id'] == note_id), None)
        if note is None:
            return False
        note.update(text=text, color=color if color in {c['color'] for c in MARKER_COLORS} else '#ffe88f',
                    images=[source for source in images if isinstance(source, str) and source.startswith('data:image/png;base64,')])
        try:
            self.service.reader_store.save_note(self.reader['link'], 'es' if self.translated else 'original', self.reader_body, note)
            self.publish()
            return True
        except Exception as error:
            self.error.emit('No se pudo guardar la nota: ' + str(error))
            return False

    def note_document_of(self, quick_document):
        from .note_document import document_of
        # Keep both Qt wrappers alive, as for the article's Quick document.
        self._note_quick_document = quick_document
        self._note_document = document_of(quick_document)
        return self._note_document

    @Slot(str, result=str)
    def note_html(self, note_id):
        from .note_document import note_html
        record = self.service.reader_store.note_record(note_id)
        return note_html(record[3]) if record else ''

    @Slot(str, QObject, str, str, result=bool)
    def save_note_document(self, note_id, quick_document, color, theme):
        try:
            record = self.service.reader_store.note_record(note_id)
            if not record:
                return False
            link, language, body, note = record
            document = self.note_document_of(quick_document)
            note.update(text=document.toPlainText().replace('\ufffc', ''), html=document.toHtml(), images=[],
                        color=color if color in {item['color'] for item in MARKER_COLORS} else '#ffe88f',
                        theme=theme if theme in {'periodico', 'gris', 'postit'} else 'periodico')
            self.service.reader_store.save_note(link, language, body, note)
            self.publish()
            return True
        except Exception as error:
            self.error.emit('No se pudo guardar la nota: ' + str(error))
            return False

    @Slot(QObject, int, str, str, result=int)
    def note_insert_image(self, quick_document, position, source, alignment):
        from .note_document import insert_image
        return insert_image(self.note_document_of(quick_document), position, source, alignment)

    @Slot(QObject, result='QVariantList')
    def note_image_layout(self, quick_document):
        from .note_document import image_layout
        return image_layout(self.note_document_of(quick_document))

    @Slot(QObject, int, int, str, float, result=int)
    def note_change_image(self, quick_document, position, target, alignment, width):
        from .note_document import change_image
        return change_image(self.note_document_of(quick_document), position, target, alignment, width)

    @Slot(QObject, int, result=bool)
    def note_remove_image(self, quick_document, position):
        from .note_document import remove_image
        return remove_image(self.note_document_of(quick_document), position)

    @Slot(str, result=bool)
    def delete_note(self, note_id):
        try:
            record = self.service.reader_store.note_record(note_id)
            if not record:
                return False
            self.service.reader_store.delete_note(note_id, *record[:3])
            self.publish()
            return True
        except Exception as error:
            self.error.emit('No se pudo eliminar la nota: ' + str(error))
            return False

    @Slot(str, result=str)
    def import_note_image(self, url):
        try:
            path = QUrl(url).toLocalFile()
            if not path or Path(path).stat().st_size > 20 * 1024 * 1024:
                raise ValueError('Selecciona una imagen local de hasta 20 MB.')
            with Image.open(path) as source:
                from PIL import ImageOps
                image = ImageOps.exif_transpose(source)
                image.thumbnail((1600, 1600))
                # Transparent breathing room survives rich-text HTML round trips.
                image = ImageOps.expand(image.convert('RGBA'), border=max(1, round(image.width * 0.04)),
                                        fill=(0, 0, 0, 0))
                image.thumbnail((1600, 1600))
                buffer = io.BytesIO()
                image.save(buffer, format='PNG')
            return 'data:image/png;base64,' + base64.b64encode(buffer.getvalue()).decode('ascii')
        except Exception as error:
            self.error.emit('No se pudo adjuntar la imagen: ' + str(error))
            return ''

    def persist_marks(self):
        if self._document_key:
            link, language, body = self._document_key
            try:
                self.service.reader_store.save_marks(link, language, body, self.marks)
                if self.marks and self.reader and not self.service.library.contains('guardados', link):
                    self.service.library.save('guardados', self.reader)
                    self.publish()
            except Exception as error:
                self.error.emit('No se pudo guardar el destacado: ' + str(error))

    def document_length(self):
        if not self._document:
            return 0
        import shiboken6
        if not shiboken6.isValid(self._document):
            self._document = None
            return 0
        return self._document.characterCount() - 1

    def normalize_marks(self, marks):
        """Keep contiguous paint of the same color as one erasable block."""
        length = self.document_length()
        valid = []
        for start, end, color in marks:
            start, end = max(0, start), min(length, end)
            if start < end and QColor(color).isValid():
                valid.append((start, end, QColor(color).name()))
        result = []
        for start, end, color in sorted(valid):
            if result and result[-1][2] == color and result[-1][1] >= start:
                result[-1] = (result[-1][0], max(result[-1][1], end), color)
            else:
                result.append((start, end, color))
        return result

    def commit_marks(self, marks):
        marks = self.normalize_marks(marks)
        if marks != self.marks:
            self.marks = marks
            self.persist_marks()
            self.render_document()

    @Slot(int, int, str)
    def mark(self, start, end, color):
        if not color:
            self.remove_marks(start, end)
            return
        start, end = sorted((start, end))
        start, end = max(0, start), min(end, self.document_length())
        if start >= end or not QColor(color).isValid():
            return
        remaining = []
        for a,b,c in self.marks:
            if b <= start or a >= end:
                remaining.append((a,b,c))
            else:
                if a < start: remaining.append((a,start,c))
                if b > end: remaining.append((end,b,c))
        # Painting is idempotent: overlap never toggles existing paint off.
        remaining.append((start, end, color))
        self.commit_marks(remaining)

    @Slot(int, int)
    def remove_marks(self, start, end):
        start, end = sorted((start, end))
        length = self.document_length()
        if not length or end < 0 or start >= length:
            return
        start, end = max(0, start), min(length, end)
        marks = self.normalize_marks(self.marks)
        # Erase whole touched blocks, both for a click and for a dragged range.
        self.commit_marks([(a, b, c) for a, b, c in marks
                           if not (a <= start < b if start == end else a < end and b > start)])

    @Slot(int)
    def remove_mark_at(self, position):
        self.remove_marks(position, position)

    def _notify_document_layout(self, *args):
        self.document_layout_changed.emit()

    def layout_image_margins(self, doc):
        """Flow paragraphs beside images without inserting annotation characters."""
        entries = self.inline_images()
        # Work on a copy: resetting margins on the live document would cause
        # repeated relayout signals and visible jumps on every measurement.
        measure = doc.clone()
        width = max(1, doc.textWidth() if doc.textWidth() > 0 else 576)
        measure.setTextWidth(width)
        block = measure.begin()
        while block.isValid():
            fmt = block.blockFormat()
            fmt.setLeftMargin(0)
            fmt.setBottomMargin(0)
            QTextCursor(block).setBlockFormat(fmt)
            block = block.next()
        groups = {}
        for entry in entries:
            position = measure.findBlock(min(entry['position'], measure.characterCount() - 1)).position()
            groups.setdefault(position, []).append(entry)
        layout = measure.documentLayout()
        images, previous_bottom = [], -12
        for position, group in groups.items():
            layout.documentSize()
            anchor = measure.findBlock(position)
            rect = layout.blockBoundingRect(anchor)
            y = max(rect.bottom() + 12, previous_bottom + 12)
            following = anchor.next()
            while following.isValid() and not following.text().strip():
                following = following.next()
            beside = width >= 520 and following.isValid() and len(group) == 1
            if beside:
                entry = group[0]
                ratio = image_ratio(entry['source'])
                image_width = min(width * 0.40, 300, 420 * ratio)
                image_height = image_width / ratio
                images.append(dict(entry, x=0, y=y, width=image_width, height=image_height, beside=True,
                                   anchor_position=position, anchor_offset=y-rect.bottom()))
                previous_bottom = y + image_height
                fmt = anchor.blockFormat()
                fmt.setBottomMargin(y - rect.bottom())
                QTextCursor(anchor).setBlockFormat(fmt)
                block = anchor.next()
                while block.isValid():
                    rect = layout.blockBoundingRect(block)
                    if rect.top() >= previous_bottom + 12:
                        break
                    fmt = block.blockFormat()
                    fmt.setLeftMargin(image_width + 18)
                    QTextCursor(block).setBlockFormat(fmt)
                    block = block.next()
            else:
                for entry in group:
                    ratio = image_ratio(entry['source'])
                    image_width = min(width, 700 * ratio)
                    image_height = image_width / ratio
                    images.append(dict(entry, x=(width-image_width)/2, y=y, width=image_width, height=image_height, beside=False,
                                       anchor_position=position, anchor_offset=y-rect.bottom()))
                    previous_bottom = y + image_height
                    y = previous_bottom + 12
                fmt = anchor.blockFormat()
                fmt.setBottomMargin(y - rect.bottom())
                QTextCursor(anchor).setBlockFormat(fmt)
        block, target = measure.begin(), doc.begin()
        while block.isValid() and target.isValid():
            wanted, actual = block.blockFormat(), target.blockFormat()
            if (wanted.leftMargin(), wanted.bottomMargin()) != (actual.leftMargin(), actual.bottomMargin()):
                actual.setLeftMargin(wanted.leftMargin())
                actual.setBottomMargin(wanted.bottomMargin())
                QTextCursor(target).setBlockFormat(actual)
            block, target = block.next(), target.next()
        actual_layout = doc.documentLayout()
        actual_layout.documentSize()
        for entry in images:
            anchor = doc.findBlock(entry.pop('anchor_position'))
            entry['y'] = actual_layout.blockBoundingRect(anchor).bottom() + entry.pop('anchor_offset')
        return images

    @Slot(QObject, result='QVariantList')
    def reader_image_layout(self, quick_document):
        return self.layout_image_margins(quick_document.textDocument())

    def render_document(self):
        doc = self._document
        if not doc:
            return
        try:
            cursor = QTextCursor(doc)
            self.layout_image_margins(doc)
            cursor.select(QTextCursor.Document)
            fmt = QTextCharFormat()
            fmt.setBackground(QColor('transparent'))
            fmt.setForeground(QColor(self.palette()['text']))
            cursor.mergeCharFormat(fmt)
            def apply(a,b,bg,fg):
                cursor.setPosition(a)
                cursor.setPosition(b,QTextCursor.KeepAnchor)
                style = QTextCharFormat()
                style.setBackground(QColor(bg)); style.setForeground(QColor(fg))
                cursor.mergeCharFormat(style)
            for a,b,c in self.marks:
                apply(a,b,c,'#171717')
            positions = self.document_matches()
            for a,b in positions:
                apply(a,b,self.palette()['accent'],self.palette()['accent_text'])
        except RuntimeError:
            self._document = None

    def document_matches(self):
        if not self._document or not self.find_text:
            return []
        text = self._document.toPlainText()
        def utf16(pos): return len(text[:pos].encode('utf-16-le'))//2
        return [(utf16(a),utf16(b)) for a,b in find_matches(text,self.find_text)]

    @Slot(str)
    def search_document(self, query):
        self.find_text, self.find_index = query, -1
        self.render_document()
        self.next_match()

    @Slot()
    def next_match(self):
        matches = self.document_matches()
        if matches:
            self.find_index = (self.find_index+1)%len(matches)
            self.document_search.emit(matches[self.find_index][0], len(matches))
        else:
            self.document_search.emit(-1,0)
