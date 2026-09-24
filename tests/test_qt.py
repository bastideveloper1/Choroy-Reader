import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('QT_QUICK_BACKEND','software')
os.environ.setdefault('QT_QUICK_CONTROLS_STYLE','Basic')
import tempfile
import unittest
from pathlib import Path
from datetime import datetime
from PySide6.QtCore import QUrl, QObject, Qt, QPoint, QCoreApplication
from PySide6.QtGui import QGuiApplication, QTextDocument, QTextCursor
from PySide6.QtQuick import QQuickWindow, QQuickItem
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtTest import QTest
from minimalfeed.backend import Backend
from minimalfeed.service import Service

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

    def test_destacado_multilinea_y_cambio_color(self):
        doc=QTextDocument(self.article['cuerpo'])
        self.backend.attachDocument(doc)
        self.backend.mark(2,40,'#b9a0ff')
        self.backend.mark(42,55,'#7bc3ff')
        self.assertEqual(self.backend.marks,[(2,40,'#b9a0ff'),(42,55,'#7bc3ff')])
        cursor=QTextCursor(doc);cursor.setPosition(30);cursor.movePosition(QTextCursor.Right,QTextCursor.KeepAnchor)
        self.assertEqual(cursor.charFormat().background().color().name(),'#b9a0ff')
        self.backend.mark(46,51,'#ffe88f')
        self.assertIn((2,40,'#b9a0ff'),self.backend.marks)
        self.assertIn((42,46,'#7bc3ff'),self.backend.marks)
        self.backend.removeMarkAt(30)
        self.assertNotIn((2,40,'#b9a0ff'),self.backend.marks)

    def test_busqueda_qt_respeta_destacados_y_unicode(self):
        doc=QTextDocument('😀 Información y MÁS información')
        self.backend.attachDocument(doc)
        self.backend.mark(3,14,'#b9a0ff')
        self.backend.searchDocument('informacion')
        self.assertEqual(len(self.backend.document_matches()),2)
        self.assertEqual(self.backend.document_matches()[0][0],3)
        self.backend.searchDocument('')
        self.assertEqual(self.backend.marks,[(3,14,'#b9a0ff')])

    def test_guardados_y_descargas_persisten(self):
        self.backend.toggleSaved(self.article['link'])
        self.backend.toggleDownload(self.article['link'])
        for _ in range(50):
            QTest.qWait(20)
            if not self.backend.downloads:break
        self.assertTrue(self.service.library.contiene('descargas',self.article['link']))
        self.backend.navigate('guardados','','')
        self.assertEqual(len(self.backend.state['articles']),1)
        self.backend.toggleSaved(self.article['link'])
        self.assertEqual(self.backend.state['articles'],[])
        self.backend.toggleDownload(self.article['link'])
        self.assertFalse(self.service.library.contiene('descargas',self.article['link']))

    def load_qml(self):
        self.engine=QQmlApplicationEngine()
        self.engine.rootContext().setContextProperty('backend',self.backend)
        self.engine.load(QUrl.fromLocalFile(str(ROOT/'minimalfeed/qml/Main.qml')))
        self.assertTrue(self.engine.rootObjects())
        QTest.qWait(120)
        return self.engine.rootObjects()[0]

    def test_qml_pantallas_logo_y_lector(self):
        root=self.load_qml()
        logo=root.findChild(QObject,'appLogo')
        self.assertIsNotNone(logo)
        self.assertTrue(logo.property('source').toLocalFile().endswith('minimalfeed-logo.png'))
        for page in ('design','sources','radar','guardados','descargas','feed'):
            self.backend.navigate(page,'','');QTest.qWait(60)
        self.backend.openArticle(self.article['link'])
        for _ in range(20):
            QTest.qWait(20)
            if self.backend.state['reader'].get('body'):break
        reader=root.findChild(QObject,'articleText')
        self.assertIsNotNone(reader)
        self.assertEqual(reader.property('text'),self.article['cuerpo'])
        self.backend.mark(1,35,'#b9a0ff')
        QTest.qWait(50)
        self.assertEqual(self.backend.marks,[(1,35,'#b9a0ff')])
        self.backend.searchDocument('informacion')
        QTest.qWait(30)
        self.assertEqual(len(self.backend.document_matches()),1)
        self.backend.prepareQuote('Primera línea de texto.')
        self.backend.updateQuote(False,False,'periodico')
        for _ in range(60):
            QTest.qWait(20)
            if not self.backend.quote_busy:break
        self.assertTrue(self.backend.state['quoteCanSave'])
        target=Path(self.tmp.name)/'cita.jpg'
        self.backend.exportQuote(QUrl.fromLocalFile(str(target)).toString())
        self.assertTrue(target.exists())
        self.backend.closeArticle();QTest.qWait(30)
        self.assertIsNotNone(root.findChild(QObject,'titleSearch'))

    def test_busqueda_desde_teclado_en_qml(self):
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
