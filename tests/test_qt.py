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

    def test_disabling_translation_updates_loaded_cards(self):
        self.article.update(titulo_es='Traducción', traducir_es=True)
        self.assertTrue(self.backend.article_view(self.article)['show_translation'])
        source=self.service.config['categorias'][0]['sitios'][0]
        source['traduccion_es']=False
        self.assertFalse(self.backend.article_view(self.article)['show_translation'])
        source['traduccion_es']=True
        self.assertTrue(self.backend.article_view(self.article)['show_translation'])

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
        for page in ('design','sources','radar','guardados','descargas','feed'):
            self.backend.navigate(page,'','');QTest.qWait(60)
        self.backend.open_article(self.article['link'])
        for _ in range(20):
            QTest.qWait(20)
            if self.backend.state['reader'].get('body'):break
        reader=root.findChild(QObject,'article_text')
        self.assertIsNotNone(reader)
        self.assertEqual(reader.property('text'),self.article['cuerpo'])
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
