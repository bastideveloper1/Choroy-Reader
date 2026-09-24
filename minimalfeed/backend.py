"""Puente QObject: las tareas de red nunca modifican la interfaz desde un hilo."""
import copy
import html
import io
import threading
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from PySide6.QtCore import QObject, Signal, Property, Slot, QUrl, QStandardPaths
from PySide6.QtGui import QColor, QTextCursor, QTextCharFormat, QDesktopServices
from PIL.PngImagePlugin import PngInfo
from biblioteca import coincidencias
from . import core
from .service import Service


class Backend(QObject):
    changed = Signal()
    finished = Signal(object)
    progress = Signal(str)
    error = Signal(str)
    documentSearch = Signal(int, int)  # position, count

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
        self.translations = {}
        self.downloads = set()
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
            self.finished.emit((callback, result, error))
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
        p = core.PALETA_TEMAS.get(name, core.PALETA_TEMAS['gris'])
        light = name == 'periodico'
        return dict(bg='#e6e6e6' if light else '#111315', panel='#dedede' if light else '#191d23',
                    card='#ededed' if light else '#171717', hover='#cccccc' if light else '#29313d',
                    text='#202020' if light else '#edf1f7', muted='#626262' if light else '#8793a3',
                    border='#b7b7b7' if light else '#30363e', accent=p['base_fuerte'],
                    accentText='#ffffff' if light else '#171717', light=light)

    def title_html(self, text):
        ranges = coincidencias(text, self.query)
        p = self.palette()
        parts, previous = [], 0
        for start, end in ranges:
            parts += [html.escape(text[previous:start]), f'<span style="background-color:{p["accent"]};color:{p["accentText"]}">{html.escape(text[start:end])}</span>']
            previous = end
        return ''.join(parts) + html.escape(text[previous:])

    def article_view(self, article):
        link = article['link']
        distinct, count = self.service.score(article) if self.service.config.get('radar_activo') else (0, 0)
        return dict(link=link, title=article.get('titulo', ''), titleHtml=self.title_html(article.get('titulo', '')),
                    translation=article.get('titulo_es') or '', translationHtml=self.title_html(article.get('titulo_es') or ''),
                    showTranslation=bool(self.service.config.get('mostrar_titulo_es', True) and article.get('traducir_es')), source=article.get('fuente', ''),
                    image=self.service.image_url(article.get('imagen')), date=core.fecha_relativa(article.get('fecha')),
                    saved=self.service.library.contiene('guardados', link), downloaded=self.service.library.contiene('descargas', link),
                    downloading=link in self.downloads, seen=link in self.service.seen,
                    radar=min(3, distinct), interests=distinct, mentions=count)

    def publish(self):
        cfg = self.service.config
        themes = [dict(key=k, name=v, color=core.PALETA_TEMAS[k]['base_fuerte']) for k, v in core.NOMBRES_TEMAS.items()]
        categories = []
        for ci, cat in enumerate(cfg['categorias']):
            sources = []
            for si, src in enumerate(cat['sitios']):
                sources.append(dict(index=si, name=src['nombre'], url=src['url'], feed=src.get('url_feed') or '',
                                    maximum=src.get('max_articulos') or 3, translate=src.get('modo_titulo', 'en_es') != 'solo_ingles' and src.get('traduccion_es', True),
                                    icon=QUrl.fromLocalFile(src['favicon_personalizado']).toString() if src.get('favicon_personalizado') else ''))
            categories.append(dict(index=ci, name=cat['nombre'], sources=sources))
        reader = self.article_view(self.reader) if self.reader else {}
        if reader:
            reader.update(body=self.reader_body, status=self.reader_status, translated=self.translated,
                          translating=self.translating, ready=bool(self.reader.get('cuerpo')),
                          showImage=cfg.get('mostrar_imagenes_lectura', True))
        self._state = dict(page=self.page, category=self.category, source=self.source, query=self.query,
                           palette=self.palette(), theme=cfg.get('color', 'gris'), themes=themes, categories=categories,
                           columns=cfg.get('articulos_por_fila', 5), showImages=cfg.get('mostrar_imagenes_lectura', True),
                           translateTitles=cfg.get('mostrar_titulo_es', True), radar=cfg.get('radar_activo', False),
                           radarWords=', '.join(cfg.get('radar_palabras', [])), radarBusy=self.radar_busy,
                           busy=self.busy, status=self.status, reader=reader,
                           articles=[self.article_view(a) for a in self.service.filtered(self.page, self.category, self.source, self.query)] if self.page in {'feed','guardados','descargas'} else [],
                           logo=QUrl.fromLocalFile(str(self.asset_dir / 'minimalfeed-logo.png')).toString(),
                           quotePreview=self.quote_preview, quoteBusy=self.quote_busy,
                           quoteCanSave=self.quote_image is not None and not self.quote_busy,
                           quoteHasImage=bool(self.quote_data and self.quote_data['article'].get('imagen')),
                           quoteIsTranslated=bool(self.quote_data and self.quote_data['translated']),
                           downloadsFolder=QUrl.fromLocalFile(QStandardPaths.writableLocation(QStandardPaths.DownloadLocation)).toString())
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
                self.analyzeRadar()
        self.background(lambda: self.service.refresh(lambda n,t: self.progress.emit(f'Cargando fuentes: {n}/{t}')), done)

    @Slot(str, str, str)
    def navigate(self, page, category='', source=''):
        self.reader_token += 1
        self.page, self.category, self.source = page, category, source
        self.reader = None
        self.reader_body = ''
        self.publish()

    @Slot(str)
    def searchTitles(self, query):
        self.query = query.strip()
        self.publish()

    @Slot(str)
    def setTheme(self, theme):
        if theme in core.PALETA_TEMAS:
            self.service.config.update(color=theme, tema=theme)
            self.service.save_config()
            self.publish()
            self.render_document()

    @Slot(int, bool, bool)
    def setDesign(self, columns, images, translations):
        self.service.config.update(articulos_por_fila=max(1,min(5,columns)), mostrar_imagenes_lectura=images,
                                   mostrar_titulo_es=translations)
        self.service.save_config()
        self.publish()

    @Slot()
    def toggleRadar(self):
        self.service.config['radar_activo'] = not self.service.config.get('radar_activo', False)
        self.service.save_config()
        self.publish()
        self.analyzeRadar()

    @Slot(str)
    def saveRadar(self, words):
        self.service.config['radar_palabras'] = list(dict.fromkeys(p.strip() for p in words.split(',') if p.strip()))
        self.service.save_config()
        self.publish()
        self.analyzeRadar()

    @Slot()
    def analyzeRadar(self):
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
    def openArticle(self, link):
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
    def closeArticle(self):
        self.reader_token += 1
        self.reader = None
        self.reader_body = ''
        self.publish()

    @Slot()
    def translateArticle(self):
        if not self.reader or not self.reader.get('cuerpo') or self.translating:
            return
        if self.translated:
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
                self.translations[link] = value
                self.reader_body, self.translated = value, True
                self.reader_status = 'Versión en español · Traducción automática'
            self.publish()
        if link in self.translations:
            done(self.translations[link], None)
        else:
            self.translating = True
            self.publish()
            body = self.reader['cuerpo']
            self.background(lambda: self.service.translate(body), done)

    def get_article(self, link):
        return self.reader if self.reader and self.reader['link'] == link else self.service.article(link)

    @Slot(str)
    def toggleSaved(self, link):
        article = self.get_article(link)
        if not article:
            return
        try:
            if self.service.library.contiene('guardados', link):
                self.service.library.borrar('guardados', link)
            else:
                self.service.library.guardar('guardados', article)
            self.publish()
        except Exception as e:
            self.error.emit(str(e))

    @Slot(str)
    def toggleDownload(self, link):
        if link in self.downloads:
            return
        article = self.get_article(link)
        if not article:
            return
        if self.service.library.contiene('descargas', link):
            try:
                self.service.library.borrar('descargas', link)
                self.publish()
            except Exception as e:
                self.error.emit(str(e))
            return
        self.downloads.add(link)
        self.publish()
        def work():
            result = self.service.read(article)
            self.service.library.guardar('descargas', result)
        def done(value, error):
            self.downloads.discard(link)
            if error:
                self.error.emit(error)
            else:
                self.status = 'Artículo disponible sin conexión'
            self.publish()
        self.background(work, done)

    @Slot(str)
    def openUrl(self, url):
        if QUrl(url).scheme() in {'https', 'http'}:
            QDesktopServices.openUrl(QUrl(url))

    @Slot(int, str)
    def saveCategory(self, index, name):
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
    def deleteCategory(self, index):
        cats = self.service.config['categorias']
        if 0 <= index < len(cats):
            if cats[index]['sitios']:
                self.error.emit('Mueve o elimina las fuentes antes de borrar la categoría')
                return
            cats.pop(index)
            self.service.save_config()
            self.publish()

    @Slot(int, int)
    def moveCategory(self, index, delta):
        cats = self.service.config['categorias']
        if 0 <= index < len(cats) and 0 <= index+delta < len(cats):
            cats.insert(index+delta, cats.pop(index))
            self.service.save_config()
            self.publish()

    @Slot(int, int, int, str, str, str, int, bool, str)
    def saveSource(self, category, index, destination, name, url, feed, maximum, translate, icon):
        cats = self.service.config['categorias']
        if not (0 <= destination < len(cats)) or not name.strip() or not url.strip():
            self.error.emit('Completa nombre, dirección y categoría')
            return
        url = url.strip()
        if '://' not in url:
            url = 'https://' + url
        if QUrl(url).scheme() not in {'http','https'} or (feed and QUrl(feed).scheme() not in {'http','https'}):
            self.error.emit('La dirección debe comenzar con http:// o https://')
            return
        source = core.sitio(name.strip(), url)
        position = len(cats[destination]['sitios'])
        if index >= 0 and 0 <= category < len(cats) and index < len(cats[category]['sitios']):
            source = cats[category]['sitios'][index].copy()
            if destination == category:
                position = index
            cats[category]['sitios'].pop(index)
        source.update(nombre=name.strip(), url=url, url_feed=feed.strip() or None, max_articulos=max(1,maximum),
                      modo_titulo='en_es' if translate else 'solo_ingles', traduccion_es=translate,
                      favicon_personalizado=QUrl(icon).toLocalFile() if icon.startswith('file:') else icon or None)
        cats[destination]['sitios'].insert(position, source)
        self.service.save_config()
        self.status = 'Fuente guardada · Pulsa Actualizar feed para cargarla'
        self.publish()

    @Slot(int, int)
    def deleteSource(self, category, index):
        cats = self.service.config['categorias']
        if 0 <= category < len(cats) and 0 <= index < len(cats[category]['sitios']):
            cats[category]['sitios'].pop(index)
            self.service.save_config()
            self.publish()

    @Slot(int, int, int)
    def moveSource(self, category, index, delta):
        sources = self.service.config['categorias'][category]['sitios']
        if 0 <= index+delta < len(sources):
            sources.insert(index+delta, sources.pop(index))
            self.service.save_config()
            self.publish()

    @Slot(str)
    def prepareQuote(self, text):
        if not self.reader or not text.strip() or len(text.strip()) > 500:
            self.error.emit('Selecciona un fragmento de hasta 500 caracteres')
            return
        self.quote_data = dict(text=text.strip(), article=dict(self.reader), translated=self.translated)
        self.quote_translation = text.strip() if self.translated else None
        self.quote_image = None
        self.quote_preview = ''
        self.publish()

    @Slot(bool, bool, str)
    def updateQuote(self, spanish, image, theme):
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
            img = core.crear_imagen_cita(text, a.get('fuente',''), a['link'], spanish,
                    titulo=a.get('titulo',''), color=core.PALETA_TEMAS[theme]['base_fuerte'],
                    imagen_bytes=a.get('imagen') if image else None, idioma_original=a.get('idioma_original',''), tema=theme)
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
    def exportQuote(self, url):
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

    @Slot(QObject)
    def attachDocument(self, quick_document):
        # Keep the Qt Quick wrapper alive alongside its document.
        self._quick_document = quick_document
        self._document = quick_document.textDocument() if hasattr(quick_document, 'textDocument') else quick_document
        self.marks, self.find_text, self.find_index = [], '', -1

    @Slot(int, int, str)
    def mark(self, start, end, color):
        if not self._document:
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
        self.render_document()

    @Slot(int)
    def removeMarkAt(self, position):
        self.marks = [(a,b,c) for a,b,c in self.marks if not a <= position < b]
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
                apply(a,b,self.palette()['accent'],self.palette()['accentText'])
        except RuntimeError:
            self._document = None

    def document_matches(self):
        if not self._document or not self.find_text:
            return []
        text = self._document.toPlainText()
        def utf16(pos): return len(text[:pos].encode('utf-16-le'))//2
        return [(utf16(a),utf16(b)) for a,b in coincidencias(text,self.find_text)]

    @Slot(str)
    def searchDocument(self, query):
        self.find_text, self.find_index = query, -1
        self.render_document()
        self.nextMatch()

    @Slot()
    def nextMatch(self):
        matches = self.document_matches()
        if matches:
            self.find_index = (self.find_index+1)%len(matches)
            self.documentSearch.emit(matches[self.find_index][0], len(matches))
        else:
            self.documentSearch.emit(-1,0)
