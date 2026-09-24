"""Puente QObject: las tareas de red nunca modifican la interfaz desde un hilo."""
import html
import io
import threading
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from PySide6.QtCore import QObject, Signal, Property, Slot, QUrl, QStandardPaths
from PySide6.QtGui import QColor, QTextCursor, QTextCharFormat, QDesktopServices
from PIL.PngImagePlugin import PngInfo
from choroy_reader.library import find_matches
from . import core


class Backend(QObject):
    changed = Signal()
    finished = Signal(object)
    progress = Signal(str)
    error = Signal(str)
    document_search = Signal(int, int)  # position, count

    def __init__(self, service, asset_dir, parent=None):
        super().__init__(parent)
        self.service = service
        self.asset_dir = Path(asset_dir)
        self.page, self.category, self.source, self.query = 'feed', '', '', ''
        self.status = 'Listo'
        self.busy = False
        self.radar_busy = False
        self.reader = None
        self.reader_body = ''
        self.reader_status = ''
        self.translated = False
        self.translating = False
        self.downloads = set()
        self.bulk_busy = False
        self._document_key = None
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
        self.publish()

    def background(self, work, callback):
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
        try:
            callback(value, error)
        except Exception as e:
            self.error.emit(str(e))

    @Slot(str)
    def _progress(self, value):
        self.status = value
        self.publish()

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
        distinct, count = self.service.score(article) if self.service.config.get('radar_activo') else (0, 0)
        return dict(link=link, title=article.get('titulo', ''), title_html=self.title_html(article.get('titulo', '')),
                    translation=article.get('titulo_es') or '', translation_html=self.title_html(article.get('titulo_es') or ''),
                    show_translation=bool(self.service.config.get('mostrar_titulo_es', True) and translate_enabled and article.get('traducir_es')), source=article.get('fuente', ''),
                    image=self.service.image_url(article.get('imagen')), date=core.relative_date(article.get('fecha')),
                    saved=self.service.library.contains('guardados', link), downloaded=self.service.library.contains('descargas', link),
                    downloading=link in self.downloads, seen=link in self.service.seen,
                    radar=min(3, distinct), interests=distinct, mentions=count)

    def publish(self):
        cfg = self.service.config
        themes = [dict(key=k, name=v, color=core.THEME_PALETTE[k]['base_fuerte']) for k, v in core.THEME_NAMES.items()]
        categories = []
        for ci, cat in enumerate(cfg['categorias']):
            sources = []
            for si, src in enumerate(cat['sitios']):
                sources.append(dict(index=si, shortcut=src.get('source_type') == 'shortcut', no_feed=bool(src.get('sin_feed')) and src.get('source_type') != 'shortcut', name=src['nombre'], url=src['url'], feed=src.get('url_feed') or '',
                                    maximum=src.get('max_articulos') or 3, translate=src.get('modo_titulo', 'en_es') != 'solo_ingles' and src.get('traduccion_es', True),
                                    icon=self.service.favicon_url(src)))
            categories.append(dict(index=ci, name=cat['nombre'], sources=sorted(sources, key=lambda source: source['no_feed'])))
        reader = self.article_view(self.reader) if self.reader else {}
        if reader:
            reader.update(body=self.reader_body, status=self.reader_status, translated=self.translated,
                          translating=self.translating, ready=bool(self.reader.get('cuerpo')),
                          show_image=cfg.get('mostrar_imagenes_lectura', True))
        self._state = dict(page=self.page, category=self.category, source=self.source, query=self.query,
                           link_sources=[src for cat in categories if not self.category or cat['name'] == self.category for src in cat['sources'] if (src['no_feed'] or src['shortcut']) and (not self.source or src['url'] == self.source)],
                           palette=self.palette(), theme=cfg.get('color', 'gris'), themes=themes, categories=categories,
                           columns=cfg.get('articulos_por_fila', 5), show_images=cfg.get('mostrar_imagenes_lectura', True),
                           translate_titles=cfg.get('mostrar_titulo_es', True), radar=cfg.get('radar_activo', False),
                           radar_words=list(cfg.get('radar_palabras', [])), radar_busy=self.radar_busy,
                           total_articles=len(self.service.all_articles()), bulk_busy=self.bulk_busy, busy=self.busy, status=self.status, reader=reader,
                           articles=[self.article_view(a) for a in self.service.filtered(self.page, self.category, self.source, self.query)] if self.page in {'feed','guardados','descargas'} else [],
                           logo=QUrl.fromLocalFile(str(self.asset_dir / 'choroy_reader_logo.png')).toString(),
                           quote_preview=self.quote_preview, quote_busy=self.quote_busy,
                           quote_can_save=self.quote_image is not None and not self.quote_busy,
                           quote_has_image=bool(self.quote_data and self.quote_data['article'].get('imagen')),
                           quote_is_translated=bool(self.quote_data and self.quote_data['translated']),
                           downloads_folder=QUrl.fromLocalFile(QStandardPaths.writableLocation(QStandardPaths.DownloadLocation)).toString())
        self.changed.emit()

    @Slot()
    def refresh(self):
        if self.busy:
            return
        self.busy, self.status = True, 'Actualizando…'
        self.publish()
        def done(value, error):
            self.busy = False
            if error:
                self.status = 'Error al actualizar'
                self.error.emit(error)
            else:
                errors = self.service.apply_refresh(value)
                self.status = 'Última actualización: ' + datetime.now().strftime('%H:%M')
                if errors:
                    self.status += f' · {len(errors)} fuentes sin respuesta'
            self.publish()
            if not error:
                self.analyze_radar()
        self.background(lambda: self.service.refresh(lambda n,t: self.progress.emit(f'Cargando fuentes: {n}/{t}')), done)

    @Slot(str, str, str)
    def navigate(self, page, category='', source=''):
        self.reader_token += 1
        self.page, self.category, self.source = page, category, source
        self.reader = None
        self.reader_body = ''
        self.publish()

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

    @Slot(int, bool, bool)
    def set_design(self, columns, images, translations):
        self.service.config.update(articulos_por_fila=max(1,min(5,columns)), mostrar_imagenes_lectura=images,
                                   mostrar_titulo_es=translations)
        self.service.save_config()
        self.publish()

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
        self.service.save_config()
        self.publish()
        self.analyze_radar()

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
    def open_article(self, link):
        article = self.service.article(link)
        if not article:
            return
        offline = self.page == 'descargas'
        self.reader_token += 1
        token = self.reader_token
        self.reader, self.reader_body, self.reader_status = dict(article), '', 'Cargando artículo…'
        self.translated, self.translating = False, False
        self.service.seen.add(link)
        self.service.save_config()
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

    @Slot(str)
    def toggle_saved(self, link):
        article = self.get_article(link)
        if not article:
            return
        try:
            if self.service.library.contains('guardados', link):
                self.service.library.delete('guardados', link)
            else:
                self.service.library.save('guardados', article)
            self.publish()
        except Exception as e:
            self.error.emit(str(e))

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
    def save_category(self, index, name):
        name = name.strip()
        cats = self.service.config['categorias']
        if not name or any(c['nombre'] == name and i != index for i,c in enumerate(cats)):
            self.error.emit('El nombre está vacío o ya existe')
            return
        if index < 0:
            cats.append(dict(nombre=name, sitios=[]))
        elif index < len(cats):
            cats[index]['nombre'] = name
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

    @Slot(int, int, int, str, str, str, int, bool, str, bool, result=bool)
    def save_source(self, category, index, destination, name, url, feed, maximum, translate, icon, shortcut=False):
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
        source['source_type'] = 'shortcut' if shortcut else 'feed'
        source.update(nombre=name.strip(), url=url, url_feed=feed.strip() or None, max_articulos=max(1,maximum),
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
                    source['sin_feed'] = not bool(found)
                    self.service.save_config()
                self.status = ('No se pudo comprobar el feed · Reintenta con Actualizar feed' if error else
                               'Fuente sin feed detectado · Disponible como enlace' if not found else
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
        self.quote_data = dict(text=text.strip(), article=dict(self.reader), translated=self.translated)
        self.quote_translation = text.strip() if self.translated else None
        self.quote_image = None
        self.quote_preview = ''
        self.publish()

    @Slot(bool, bool, str)
    def update_quote(self, spanish, image, theme):
        if not self.quote_data:
            return
        if self.quote_data['translated'] and not spanish:
            self.error.emit('Selecciona el fragmento en el original para conservar sus palabras exactas')
            return
        self.quote_token += 1
        token, data = self.quote_token, dict(self.quote_data)
        self.quote_busy = True
        self.quote_image = None
        self.publish()
        def work():
            text = data['text']
            translated_text = self.quote_translation
            if spanish:
                translated_text = translated_text or self.service.translate(text)
                text = translated_text
            a = data['article']
            img = core.create_quote_image(text, a.get('fuente',''), a['link'], spanish,
                    title=a.get('titulo',''), color=core.THEME_PALETTE[theme]['base_fuerte'],
                    image_bytes=a.get('imagen') if image else None, original_language=a.get('idioma_original',''), theme=theme)
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
                self.quote_image.save(out, 'PNG')
                self.quote_preview = self.service.image_url(out.getvalue())
            self.publish()
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
                self.quote_image.convert('RGB').save(path, 'JPEG', quality=95, subsampling=0)
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

    @Slot(bool)
    def download_all(self, include_translation):
        if self.bulk_busy:
            return
        articles = [dict(article) for article in self.service.all_articles() if article['link'] not in self.downloads]
        if not articles:
            return
        self.bulk_busy = True
        links = {article['link'] for article in articles}
        self.downloads.update(links)
        self.publish()
        def work():
            errors = []
            downloaded = 0
            for index, article in enumerate(articles, 1):
                try:
                    result = self.service.read(article)
                    self.service.library.save('descargas', result)
                    downloaded += 1
                    if include_translation:
                        self.service.translate_article(result)
                except Exception as error:
                    errors.append(article.get('titulo', article['link']) + ': ' + str(error))
                self.progress.emit(f'Preparando lectura sin conexión: {index}/{len(articles)}')
            return downloaded, errors
        def done(result, error):
            self.bulk_busy = False
            self.downloads.difference_update(links)
            if error:
                self.error.emit(error)
            else:
                count, errors = result
                self.status = f'{count} artículos disponibles sin conexión'
                if errors:
                    self.error.emit('Algunas descargas o traducciones fallaron:\n' + '\n'.join(errors))
            self.publish()
        self.background(work, done)

    @Slot(QObject)
    def attach_document(self, quick_document):
        # Keep the Qt Quick wrapper alive alongside its document.
        self._quick_document = quick_document
        self._document = quick_document.textDocument() if hasattr(quick_document, 'textDocument') else quick_document
        self.marks, self.find_text, self.find_index = [], '', -1
        self._document_key = None
        if self.reader and self.reader_body:
            language = 'es' if self.translated else 'original'
            self._document_key = (self.reader['link'], language, self.reader_body)
            self.service.reader_store.save_original(self.reader['link'], self.reader['cuerpo'])
            snapshot = self.service.reader_store.read(self.reader['link'])
            self.marks = [tuple(mark) for mark in snapshot['translated_marks' if self.translated else 'original_marks']]
        self.render_document()

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

    @Slot(int, int, str)
    def mark(self, start, end, color):
        if not self._document:
            return
        import shiboken6
        if not shiboken6.isValid(self._document):
            self._document = None
            return
        start, end = sorted((start,end))
        end = min(end, self._document.characterCount()-1)
        if start < 0 or start >= end:
            return
        remaining = []
        for a,b,c in self.marks:
            if b <= start or a >= end:
                remaining.append((a,b,c))
            else:
                if a < start: remaining.append((a,start,c))
                if b > end: remaining.append((end,b,c))
        if color:
            remaining.append((start,end,color))
        self.marks = remaining
        self.persist_marks()
        self.render_document()

    @Slot(int)
    def remove_mark_at(self, position):
        self.marks = [(a,b,c) for a,b,c in self.marks if not a <= position < b]
        self.persist_marks()
        self.render_document()

    def render_document(self):
        doc = self._document
        if not doc:
            return
        try:
            cursor = QTextCursor(doc)
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
