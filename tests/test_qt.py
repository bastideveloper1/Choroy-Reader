import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('QT_QUICK_BACKEND','software')
os.environ.setdefault('QT_QUICK_CONTROLS_STYLE','Basic')
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from datetime import datetime
from PySide6.QtCore import QUrl, QObject, Qt, QPoint, QCoreApplication, QMetaObject
from PySide6.QtGui import QGuiApplication, QTextDocument, QTextCursor
from PySide6.QtQuick import QQuickWindow, QQuickItem
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtTest import QTest
from choroy_reader.backend import Backend
from choroy_reader.service import Service

APP=QGuiApplication.instance() or QGuiApplication([])
ROOT=Path(__file__).resolve().parent.parent

class QtTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.service=Service(self.tmp.name)
        self.service.config['categorias']=[{'nombre':'Tech','sitios':[{'nombre':'Fuente','url':'https://example.com'}]}]
        self.article=dict(link='https://example.com/a',titulo='Información y seguridad',source_url='https://example.com',fuente='Fuente',fecha=datetime.now(),cuerpo='Primera línea de texto.\nSegunda línea con información.\nTercera línea.',imagen=None)
        self.service.articles={'https://example.com':[self.article]}
        self.backend=Backend(self.service,ROOT/'assets')
        self.engine=None

    def tearDown(self):
        if self.engine:
            import shiboken6
            for root in self.engine.rootObjects():
                root.close();shiboken6.delete(root)
            shiboken6.delete(self.engine)
        self.backend.deleteLater();APP.processEvents()
        self.tmp.cleanup()

    def test_annotations_survive_translation_navigation_and_restart(self):
        root = self.load_qml()
        self.backend.open_article(self.article['link'])
        for _ in range(150):
            QTest.qWait(20)
            if self.backend.reader_body:
                break
        self.assertTrue(self.backend.reader_body)
        self.backend.mark(2, 35, '#b9a0ff')
        with patch.object(self.service, 'translate', return_value='Texto traducido de prueba. Otra frase.'):
            self.backend.translate_article()
            for _ in range(100):
                QTest.qWait(20)
                if not self.backend.translating:
                    break
        self.assertTrue(self.backend.translated)
        self.assertEqual(self.backend.marks, [])
        self.backend.mark(1, 8, '#ffe88f')
        self.backend.translate_article()
        QTest.qWait(100)
        self.assertEqual(self.backend.marks, [(2, 35, '#b9a0ff')])
        self.backend.toggle_download(self.article['link'])
        for _ in range(150):
            QTest.qWait(20)
            if not self.backend.downloads:
                break
        self.backend.close_article()
        QTest.qWait(50)
        reopened_service = Service(self.tmp.name)
        reopened = Backend(reopened_service, ROOT/'assets')
        reopened.navigate('descargas', '', '')
        with patch('choroy_reader.core.download', side_effect=AssertionError('Network must not be used')):
            reopened.open_article(self.article['link'])
            for _ in range(150):
                QTest.qWait(20)
                if reopened.reader_body:
                    break
            original_document = QTextDocument(reopened.reader_body)
            reopened.attach_document(original_document)
            self.assertEqual(reopened.marks, [(2, 35, '#b9a0ff')])
            reopened.translate_article()
            translated_document = QTextDocument(reopened.reader_body)
            reopened.attach_document(translated_document)
            self.assertEqual(reopened.marks, [(1, 8, '#ffe88f')])
            self.assertEqual(reopened.reader_body, 'Texto traducido de prueba. Otra frase.')
        reopened.deleteLater()

    def test_bulk_download_keeps_cached_translation(self):
        with patch.object(self.service, 'translate', return_value='Traducción guardada'):
            self.backend.download_all(True)
            for _ in range(150):
                QTest.qWait(20)
                if not self.backend.bulk_busy:
                    break
        self.assertFalse(self.backend.bulk_busy)
        self.assertTrue(self.service.library.contains('descargas', self.article['link']))
        self.assertEqual(Service(self.tmp.name).reader_store.read(self.article['link'])['translation'], 'Traducción guardada')

    def test_cancel_refresh_preserves_feed_and_allows_retry(self):
        result = ({'https://example.com': []}, {}, [])
        with patch.object(self.backend, 'background') as background:
            self.backend.refresh()
            callback = background.call_args.args[1]
            self.assertTrue(self.backend.busy)
            self.backend.cancel_refresh()
            self.assertTrue(self.backend.state['refresh_cancelling'])
            callback(result, None)
            self.assertFalse(self.backend.busy)
            self.assertEqual(self.service.all_articles(), [self.article])
            self.backend.refresh()
            self.assertFalse(self.backend.refresh_cancel.is_set())
            background.call_args.args[1](result, None)
            self.assertEqual(self.service.all_articles(), [])

    def test_cancelled_refresh_does_not_fetch_sources(self):
        import threading
        cancel = threading.Event()
        cancel.set()
        with patch.object(self.service, 'fetch_source') as fetch:
            self.service.refresh(cancel=cancel)
        fetch.assert_not_called()

    def test_bulk_cancel_removes_new_downloads_and_preserves_existing(self):
        import threading
        existing = dict(self.article, link='https://example.com/existing')
        pending = dict(self.article, link='https://example.com/pending')
        self.service.library.save('descargas', existing)
        self.service.articles['https://example.com'] = [existing, self.article, pending]
        entered, release = threading.Event(), threading.Event()
        def read(article):
            if article['link'] == pending['link']:
                entered.set()
                release.wait(3)
            return article
        with patch.object(self.service, 'read', side_effect=read):
            self.backend.download_all(False)
            try:
                for _ in range(100):
                    QTest.qWait(10)
                    if entered.is_set():
                        break
                self.assertTrue(entered.is_set())
                self.assertTrue(self.service.library.contains('descargas', self.article['link']))
                self.backend.cancel_download_all()
                self.assertTrue(self.backend.state['bulk_cancelling'])
            finally:
                release.set()
            for _ in range(100):
                QTest.qWait(10)
                if not self.backend.bulk_busy:
                    break
        self.assertFalse(self.backend.bulk_busy)
        self.assertFalse(self.backend.downloads)
        self.assertTrue(self.service.library.contains('descargas', existing['link']))
        self.assertFalse(self.service.library.contains('descargas', self.article['link']))
        self.assertFalse(self.service.library.contains('descargas', pending['link']))
        self.backend.download_all(False)
        for _ in range(100):
            QTest.qWait(10)
            if not self.backend.bulk_busy:
                break
        self.assertFalse(self.backend.bulk_cancel.is_set())
        self.assertTrue(self.service.library.contains('descargas', pending['link']))

    def test_link_opening_uses_qt_api(self):
        with patch('choroy_reader.backend.QDesktopServices.openUrl') as opener:
            self.backend.open_url('https://example.com')
            self.assertEqual(opener.call_args.args[0].toString(), 'https://example.com')
            self.backend.open_url('file:///tmp/private')
            self.assertEqual(opener.call_count, 1)

    def test_shortcut_rejects_duplicate_in_same_category(self):
        before = list(self.service.config['categorias'][0]['sitios'])
        self.assertFalse(self.backend.save_source(0, -1, 0, 'Duplicate', 'https://example.com/', '', 3, True, '', True))
        self.assertEqual(self.service.config['categorias'][0]['sitios'], before)

    def test_source_and_offline_dialogs_open(self):
        root = self.load_qml()
        for name in ('source_editor', 'offline_dialog'):
            dialog = root.findChild(QObject, name)
            self.assertIsNotNone(dialog)
            QMetaObject.invokeMethod(dialog, 'open')
            QTest.qWait(100)
            self.assertTrue(dialog.property('visible'))
            QMetaObject.invokeMethod(dialog, 'close')

    def test_shortcut_does_not_attempt_feed_discovery(self):
        with patch.object(self.service, 'fetch_favicon'), patch('choroy_reader.core.discover_feed', side_effect=AssertionError('No RSS lookup')):
            self.backend.save_source(0, -1, 0, 'Atajo', 'https://shortcut.example', '', 3, True, '', True)
            QTest.qWait(50)
            source = self.service.config['categorias'][0]['sitios'][-1]
            _, articles = self.service.fetch_source(source, self.service.config)
        self.assertEqual(articles, [])
        shortcut = self.backend.state['link_sources'][0]
        self.assertTrue(shortcut['shortcut'])
        self.assertFalse(shortcut['no_feed'])

    def test_shortcut_visibility_is_independent_of_articles(self):
        for show_shortcut in (True, False):
            self.assertTrue(self.backend.save_source(
                0, 0, 0, 'Fuente', 'https://example.com',
                'https://example.com/rss', 3, True, '', False, show_shortcut))
            self.assertEqual(len(self.backend.state['link_sources']), int(show_shortcut))
            self.assertEqual(len(self.backend.state['articles']), 1)
            persisted = Service(self.tmp.name).config['categorias'][0]['sitios'][0]
            self.assertEqual(persisted['show_shortcut'], show_shortcut)
            self.assertEqual(persisted['source_type'], 'feed')

    def test_navigation_and_feed_toolbar_align(self):
        root = self.load_qml()
        navigation = root.findChild(QQuickItem, 'articlesNavigation')
        refresh = root.findChild(QQuickItem, 'refreshFeedButton')
        self.assertEqual(navigation.mapToScene(QPoint(0, 0)).y(),
                         refresh.mapToScene(QPoint(0, 0)).y())
        self.assertEqual(navigation.height(), refresh.height())
        self.assertEqual(navigation.property('topInset'), refresh.property('topInset'))

    def test_bilingual_radar_suggestions_scoring_and_persistence(self):
        self.backend.add_radar_word('chileno')
        article = dict(self.article, titulo='Chilean research', titulo_es='', cuerpo='Chilean scientist')
        self.assertEqual(self.service.score(article), (0, 0))
        with patch('choroy_reader.core.translate_text', side_effect=lambda word, target_language: 'Chilean' if target_language == 'en' else word):
            self.backend.set_radar_bilingual(True)
            for _ in range(100):
                QTest.qWait(10)
                if not self.backend.radar_translating:
                    break
        self.assertEqual(self.service.score(article), (1, 2))
        self.assertEqual(self.service.score(article, details=True), (1, 2, ['Chilean (2)']))
        self.service.config['radar_activo'] = True
        self.assertEqual(self.backend.article_view(article)['radar_detected'], ['Chilean (2)'])
        self.backend.save_radar_equivalents('chileno', 'Chilean, chilena, chilenos')
        self.assertEqual(self.service.score(dict(article, cuerpo='chilena y chilenos')), (1, 3))
        reopened = Service(self.tmp.name)
        self.assertEqual(reopened.score(article), (1, 2))
        self.backend.set_radar_bilingual(False)
        self.assertEqual(self.service.score(article), (0, 0))

    def test_radar_compact_tags_and_bounded_toggle(self):
        self.backend.add_radar_word('chileno')
        self.backend.save_radar_equivalents('chileno', 'Chilean')
        self.backend.navigate('radar', '', '')
        root = self.load_qml()
        toggle = root.findChild(QQuickItem, 'radarBilingualToggle')
        tags = root.findChild(QQuickItem, 'radarTags')
        self.assertLess(toggle.width(), tags.width())
        def labels():
            return [item.property('modelData')['label'] for item in tags.childItems()
                    if item.objectName() == 'radarTag']
        self.assertEqual(labels(), ['chileno'])
        outside = toggle.mapToScene(QPoint(int(toggle.width() + 15), int(toggle.height() / 2))).toPoint()
        QTest.mouseClick(root, Qt.LeftButton, Qt.NoModifier, outside)
        self.assertFalse(self.backend.state['radar_bilingual'])
        point = toggle.mapToScene(toggle.boundingRect().center()).toPoint()
        QTest.mouseClick(root, Qt.LeftButton, Qt.NoModifier, point)
        QTest.qWait(30)
        self.assertEqual(labels(), ['chileno', 'Chilean'])
        for item in tags.childItems():
            if item.objectName() == 'radarTag':
                self.assertLess(item.width(), tags.width())
        QTest.mouseClick(root, Qt.LeftButton, Qt.NoModifier, point)
        QTest.qWait(30)
        self.assertEqual(labels(), ['chileno'])

    def test_bilingual_radar_failure_keeps_original_interest(self):
        self.backend.add_radar_word('chileno')
        with patch('choroy_reader.core.translate_text', return_value=None):
            self.backend.set_radar_bilingual(True)
            for _ in range(100):
                QTest.qWait(10)
                if not self.backend.radar_translating:
                    break
        self.assertNotIn('chileno', self.service.config.get('radar_equivalencias', {}))
        self.assertEqual(self.service.score(dict(self.article, titulo='chileno', cuerpo='')), (1, 1))

    def test_disabling_translation_updates_loaded_cards(self):
        self.article.update(titulo_es='Traducción', traducir_es=True)
        self.assertTrue(self.backend.article_view(self.article)['show_translation'])
        source=self.service.config['categorias'][0]['sitios'][0]
        source['traduccion_es']=False
        self.assertFalse(self.backend.article_view(self.article)['show_translation'])
        source['traduccion_es']=True
        self.assertTrue(self.backend.article_view(self.article)['show_translation'])

    def test_highlight_drag_commits_only_final_range(self):
        self.article['cuerpo'] = 'abcdefghijklmnopqrstuvwxyz ' * 12
        root = self.load_qml()
        self.backend.open_article(self.article['link'])
        for _ in range(100):
            QTest.qWait(10)
            if self.backend.reader_body:
                break
        QTest.qWait(100)
        reader = root.findChild(QQuickItem, 'reader_page')
        text = root.findChild(QQuickItem, 'article_text')
        reader.setProperty('marking', True)
        start = text.mapToScene(QPoint(160, 10)).toPoint()
        far = text.mapToScene(QPoint(15, 10)).toPoint()
        final = text.mapToScene(QPoint(95, 10)).toPoint()
        with patch.object(self.backend, 'persist_marks', wraps=self.backend.persist_marks) as persist:
            QTest.mousePress(root, Qt.LeftButton, Qt.NoModifier, start)
            for point in [far, start, far, final]:
                QTest.mouseMove(root, point, 1)
            self.assertEqual(self.backend.marks, [])
            persist.assert_not_called()
            expected = (text.property('selectionStart'), text.property('selectionEnd'))
            self.assertLess(expected[0], expected[1])
            QTest.mouseRelease(root, Qt.LeftButton, Qt.NoModifier, final)
            QTest.qWait(30)
            self.assertEqual(len(self.backend.marks), 1)
            self.assertEqual(self.backend.marks[0][:2], expected)
            self.assertEqual(persist.call_count, 1)

    def test_same_highlight_color_erases_only_overlapping_section(self):
        doc = QTextDocument('abcdefghijklmnopqrstuvwxyz')
        self.backend.attach_document(doc)
        self.backend.mark(2, 20, '#b9a0ff')
        self.backend.mark(14, 6, '#B9A0FF')
        self.assertEqual(sorted(self.backend.marks), [(2, 6, '#b9a0ff'), (14, 20, '#b9a0ff')])
        self.backend.mark(14, 20, '#b9a0ff')
        self.assertEqual(self.backend.marks, [(2, 6, '#b9a0ff')])
        self.backend.mark(4, 10, '#b9a0ff')
        self.assertEqual(sorted(self.backend.marks), [(2, 4, '#b9a0ff'), (6, 10, '#b9a0ff')])
        self.backend.mark(6, 10, '#7bc3ff')
        self.assertIn((6, 10, '#7bc3ff'), self.backend.marks)

    def test_multiline_highlight_and_color_changes(self):
        doc=QTextDocument(self.article['cuerpo'])
        self.backend.attach_document(doc)
        self.backend.mark(2,40,'#b9a0ff')
        self.backend.mark(42,55,'#7bc3ff')
        self.assertEqual(self.backend.marks,[(2,40,'#b9a0ff'),(42,55,'#7bc3ff')])
        cursor=QTextCursor(doc);cursor.setPosition(30);cursor.movePosition(QTextCursor.Right,QTextCursor.KeepAnchor)
        self.assertEqual(cursor.charFormat().background().color().name(),'#b9a0ff')
        self.backend.mark(46,51,'#ffe88f')
        self.assertIn((2,40,'#b9a0ff'),self.backend.marks)
        self.assertIn((42,46,'#7bc3ff'),self.backend.marks)
        self.backend.remove_mark_at(30)
        self.assertNotIn((2,40,'#b9a0ff'),self.backend.marks)

    def test_search_preserves_highlights_and_unicode(self):
        doc=QTextDocument('😀 Información y MÁS información')
        self.backend.attach_document(doc)
        self.backend.mark(3,14,'#b9a0ff')
        self.backend.search_document('informacion')
        self.assertEqual(len(self.backend.document_matches()),2)
        self.assertEqual(self.backend.document_matches()[0][0],3)
        self.backend.search_document('')
        self.assertEqual(self.backend.marks,[(3,14,'#b9a0ff')])

    def test_long_article_scrolls_to_read_action(self):
        self.article['cuerpo'] = ('Un párrafo largo para comprobar el desplazamiento del lector.\n' * 180)
        root = self.load_qml()
        self.backend.open_article(self.article['link'])
        for _ in range(100):
            QTest.qWait(10)
            if self.backend.reader_body:
                break
        QTest.qWait(100)
        reader = root.findChild(QQuickItem, 'reader_page')
        flickable = reader.property('contentItem')
        self.assertGreater(flickable.property('contentHeight'), reader.height())
        from PySide6.QtCore import QPointF
        point = reader.mapToScene(QPointF(reader.width() / 2, reader.height() / 2))
        QTest.wheelEvent(root, point, QPoint(0, -120))
        QTest.qWait(200)
        self.assertGreater(flickable.property('contentY'), 0)
        flickable.setProperty('contentY', flickable.property('contentHeight') - flickable.height())
        QTest.qWait(50)
        action = root.findChild(QQuickItem, 'readerReadAction')
        self.assertLess(action.mapToScene(QPointF(0, action.height())).y(), root.height() + 1)

    def test_read_articles_move_to_end_and_opening_does_not_mark_read(self):
        other = dict(self.article, link='https://example.com/other')
        self.service.articles['https://example.com'] = [self.article, other]
        self.backend.open_article(self.article['link'])
        for _ in range(100):
            QTest.qWait(10)
            if self.backend.reader_body:
                break
        self.assertNotIn(self.article['link'], self.service.seen)
        root = self.load_qml()
        self.assertIsNotNone(root.findChild(QObject, 'readerReadAction'))
        self.backend.toggle_read(self.article['link'])
        self.assertEqual([a['link'] for a in self.service.filtered()], [other['link'], self.article['link']])
        self.backend.toggle_read(self.article['link'])
        self.assertEqual(self.service.filtered()[0]['link'], self.article['link'])

    def test_dismissed_articles_sort_last_and_persist_independently(self):
        other = dict(self.article, link='https://example.com/read')
        fresh = dict(self.article, link='https://example.com/new')
        self.service.apply_refresh(({'https://example.com': [self.article, other, fresh]}, {}, []))
        self.backend.toggle_read(other['link'])
        self.backend.toggle_saved(self.article['link'])
        self.backend.toggle_dismissed(self.article['link'])
        self.assertEqual([a['link'] for a in self.service.filtered()], [fresh['link'], other['link'], self.article['link']])
        reopened = Service(self.tmp.name)
        self.assertIn(self.article['link'], reopened.dismissed)
        self.assertNotIn(self.article['link'], reopened.seen)
        self.assertTrue(reopened.library.contains('guardados', self.article['link']))
        self.service.apply_refresh(({'https://example.com': [self.article, other, fresh]}, {}, []))
        self.assertTrue(self.backend.article_view(self.article)['dismissed'])
        self.backend.toggle_dismissed(self.article['link'])
        self.assertFalse(Service(self.tmp.name).dismissed)
        self.assertEqual(self.service.filtered()[0]['link'], self.article['link'])

    def test_bulk_read_scopes_and_persistent_undo(self):
        other = dict(self.article, link='https://other.example/a', source_url='https://other.example')
        saved = dict(self.article, link='https://saved.example/a', source_url='https://saved.example')
        self.service.config['categorias'][0]['sitios'].append({'nombre': 'Otra', 'url': other['source_url']})
        self.service.articles[other['source_url']] = [other]
        self.service.library.save('guardados', saved)
        self.backend.navigate('feed', 'Tech', self.article['source_url'])
        self.backend.prepare_mark_all_read('source')
        self.assertEqual(self.backend.read_batch, {self.article['link']})
        self.backend.mark_all_read()
        self.backend.prepare_mark_all_read('category')
        self.assertEqual(self.backend.read_batch, {other['link']})
        self.backend.mark_all_read()
        self.backend.undo_mark_all_read()
        self.assertEqual(self.service.seen, {self.article['link']})
        self.backend.prepare_mark_all_read('library')
        self.assertEqual(self.backend.read_batch, {other['link'], saved['link']})
        self.backend.mark_all_read()
        reopened = Backend(Service(self.tmp.name), ROOT / 'assets')
        reopened.undo_mark_all_read()
        self.assertEqual(reopened.service.seen, {self.article['link']})
        reopened.deleteLater()

    def test_bulk_read_undo_preserves_later_manual_changes(self):
        self.backend.prepare_mark_all_read('library')
        self.backend.mark_all_read()
        self.backend.toggle_read(self.article['link'])
        self.backend.toggle_read(self.article['link'])
        self.backend.undo_mark_all_read()
        self.assertIn(self.article['link'], self.service.seen)

    def test_article_lifecycle_history_and_cached_text_survive_rss_removal(self):
        link = self.article['link']
        self.service.apply_refresh(({'https://example.com': [self.article]}, {}, []))
        self.service.read(self.article)
        self.backend.toggle_read(link)
        self.assertEqual(len(self.service.filtered()), 1)
        self.assertTrue(self.service.library.contains('feed', link))
        self.service.apply_refresh(({}, {}, ['Fuente sin respuesta']))
        self.assertEqual(len(self.service.filtered()), 1)
        self.service.apply_refresh(({'https://example.com': []}, {}, []))
        self.assertEqual(self.service.filtered(), [])
        self.assertFalse(self.service.library.contains('feed', link))
        reopened = Service(self.tmp.name)
        history = reopened.filtered('historial')
        self.assertEqual([a['link'] for a in history], [link])
        self.assertIn(link, reopened.seen)
        self.assertIsNone(history[0]['cuerpo'])
        with patch('choroy_reader.core.download', side_effect=AssertionError('No network')):
            self.assertEqual(reopened.read(reopened.article(link))['cuerpo'], self.article['cuerpo'])
        reopened.apply_refresh(({'https://example.com': [self.article, self.article]}, {}, []))
        self.assertEqual(len(reopened.filtered('historial')), 1)
        self.assertEqual(len(reopened.filtered()), 1)
        self.assertIn(link, reopened.seen)

    def test_reading_position_persists_and_keeps_languages_separate(self):
        self.service.apply_refresh(({'https://example.com': [self.article]}, {}, []))
        self.backend.reader = self.article
        self.backend.reader_body = self.article['cuerpo']
        doc = QTextDocument(self.article['cuerpo'])
        self.backend.attach_document(doc)
        self.backend.save_reading_position(20)
        entry = self.backend.state['reader']['reading_progress']
        self.assertEqual(entry['position'], 20)
        self.assertEqual(entry['percent'], round(2000 / (doc.characterCount() - 1)))
        self.assertNotIn(self.article['link'], self.service.seen)
        self.backend.translated = True
        self.backend.reader_body = 'Traducción con posición diferente'
        translated_doc = QTextDocument(self.backend.reader_body)
        self.backend.attach_document(translated_doc)
        self.backend.save_reading_position(5)
        reopened = Backend(Service(self.tmp.name), ROOT / 'assets')
        reopened.reader = self.article
        reopened.reader_body = self.article['cuerpo']
        reopened.attach_document(doc)
        reopened.publish()
        self.assertEqual(reopened.state['reader']['reading_progress']['position'], 20)
        received = []
        reopened.document_search.connect(lambda position, count: received.append(position))
        reopened.resume_reading()
        self.assertEqual(received, [20])
        self.assertEqual(reopened.service.config['progreso_lectura'][self.article['link']]['es']['position'], 5)
        reopened.deleteLater()

    def test_short_history_retention_options(self):
        for days in (1, 7):
            self.backend.set_history_retention(days)
            self.assertEqual(Service(self.tmp.name).config['historial_dias'], days)

    def test_article_states_survive_refresh_restart_and_restore(self):
        link = self.article['link']
        # Repeated entries in RSS and across sources still produce one card.
        self.service.config['categorias'][0]['sitios'].append({'nombre': 'Otra', 'url': 'https://other.example'})
        self.service.apply_refresh(({'https://example.com': [self.article, self.article],
                                     'https://other.example': [self.article]}, {}, []))
        self.assertEqual(len(self.service.all_articles()), 1)
        self.backend.toggle_read(link)
        self.backend.toggle_saved(link)
        self.backend.toggle_archived(link)
        self.assertEqual(self.service.filtered(), [])
        self.assertEqual(len(self.service.filtered('guardados')), 1)
        self.assertEqual(len(self.service.filtered('archivados')), 1)
        updated = dict(self.article, titulo='Título actualizado')
        self.service.apply_refresh(({'https://example.com': [updated, updated]}, {}, []))
        reopened = Service(self.tmp.name)
        backend = Backend(reopened, ROOT / 'assets')
        self.assertEqual(len(reopened.all_articles()), 1)
        state = backend.article_view(reopened.article(link))
        self.assertTrue(state['seen'])
        self.assertTrue(state['saved'])
        self.assertTrue(state['archived'])
        self.assertEqual(reopened.filtered(), [])
        backend.navigate('archivados', '', '')
        self.assertEqual(len(backend.state['articles']), 1)
        backend.toggle_read(link)
        backend.toggle_archived(link)
        self.assertEqual(len(reopened.filtered()), 1)
        self.assertFalse(Service(self.tmp.name).seen)
        self.assertEqual(Service(self.tmp.name).filtered('archivados'), [])
        self.assertTrue(reopened.library.contains('guardados', link))
        backend.deleteLater()

    def test_restore_archived_article_missing_from_latest_feed(self):
        self.backend.toggle_archived(self.article['link'])
        self.service.apply_refresh(({'https://example.com': []}, {}, []))
        self.assertEqual(self.service.all_articles(), [])
        self.backend.toggle_archived(self.article['link'])
        self.assertEqual(len(self.service.filtered()), 1)
        self.assertEqual(len(Service(self.tmp.name).filtered()), 1)

    def test_bookmarks_and_downloads_persist(self):
        self.backend.toggle_saved(self.article['link'])
        self.backend.toggle_download(self.article['link'])
        for _ in range(150):
            QTest.qWait(20)
            if not self.backend.downloads:break
        self.assertTrue(self.service.library.contains('descargas',self.article['link']))
        self.backend.navigate('guardados','','')
        self.assertEqual(len(self.backend.state['articles']),1)
        self.backend.toggle_saved(self.article['link'])
        self.assertEqual(self.backend.state['articles'],[])
        self.backend.toggle_download(self.article['link'])
        self.assertFalse(self.service.library.contains('descargas',self.article['link']))

    def load_qml(self):
        self.engine=QQmlApplicationEngine()
        self.engine.rootContext().setContextProperty('backend',self.backend)
        self.engine.load(QUrl.fromLocalFile(str(ROOT/'choroy_reader/qml/main.qml')))
        self.assertTrue(self.engine.rootObjects())
        QTest.qWait(120)
        return self.engine.rootObjects()[0]

    def test_qml_pages_logo_and_reader(self):
        root=self.load_qml()
        panel=root.findChild(QQuickItem,'sidebarPanel')
        toggle=root.findChild(QQuickItem,'sidebarToggle')
        self.assertTrue(panel.isVisible())
        point=toggle.mapToScene(toggle.boundingRect().center()).toPoint()
        QTest.mouseClick(root,Qt.LeftButton,Qt.NoModifier,point)
        QTest.qWait(30)
        self.assertFalse(panel.isVisible())
        QTest.mouseClick(root,Qt.LeftButton,Qt.NoModifier,point)
        QTest.qWait(30)
        self.assertTrue(panel.isVisible())
        logo=root.findChild(QObject,'appLogo')
        self.assertIsNotNone(logo)
        self.assertTrue(logo.property('source').toLocalFile().endswith('choroy_reader_logo.png'))
        for page in ('design','sources','radar','guardados','descargas','archivados','historial','feed'):
            self.backend.navigate(page,'','');QTest.qWait(60)
        self.backend.open_article(self.article['link'])
        for _ in range(20):
            QTest.qWait(20)
            if self.backend.state['reader'].get('body'):break
        reader=root.findChild(QObject,'article_text')
        self.assertIsNotNone(reader)
        self.assertEqual(reader.property('text'),self.article['cuerpo'])
        radar = root.findChild(QQuickItem, 'readerRadarBadge')
        self.assertFalse(radar.isVisible())
        self.service.config.update(radar_activo=True, radar_palabras=['información'])
        self.backend.publish()
        QTest.qWait(30)
        self.assertTrue(radar.isVisible())
        self.assertEqual(self.backend.state['reader']['radar_detected'], ['información (2)'])
        self.backend.mark(1,35,'#b9a0ff')
        QTest.qWait(50)
        self.assertEqual(self.backend.marks,[(1,35,'#b9a0ff')])
        self.backend.search_document('informacion')
        QTest.qWait(30)
        self.assertEqual(len(self.backend.document_matches()),1)
        self.backend.prepare_quote('Primera línea de texto.')
        self.backend.update_quote(False,False,'periodico')
        for _ in range(60):
            QTest.qWait(20)
            if not self.backend.quote_busy:break
        self.assertTrue(self.backend.state['quote_can_save'])
        target=Path(self.tmp.name)/'cita.jpg'
        self.backend.export_quote(QUrl.fromLocalFile(str(target)).toString())
        self.assertTrue(target.exists())
        self.backend.close_article();QTest.qWait(30)
        self.assertIsNotNone(root.findChild(QObject,'titleSearch'))

    def test_qml_keyboard_search(self):
        root=self.load_qml()
        field=root.findChild(QQuickItem,'titleSearch')
        field.forceActiveFocus()
        for key in (Qt.Key_I,Qt.Key_N,Qt.Key_F,Qt.Key_O):
            QTest.keyClick(root,key)
        QTest.qWait(250)
        self.assertEqual(self.backend.query,'info')
        self.assertEqual(len(self.backend.state['articles']),1)
        QTest.keyClick(root,Qt.Key_A,Qt.ControlModifier)
        QTest.keyClick(root,Qt.Key_Z)
        QTest.qWait(250)
        self.assertEqual(self.backend.state['articles'],[])
        QTest.keyClick(root,Qt.Key_Backspace)
        QTest.qWait(250)
        self.assertEqual(len(self.backend.state['articles']),1)

if __name__=='__main__':unittest.main()
