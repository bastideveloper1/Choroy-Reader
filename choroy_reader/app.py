"""Arranque Qt Quick. --no-network permite revisar la interfaz sin descargar feeds."""
import argparse
import os
import sys
from pathlib import Path
from datetime import datetime, timezone
from PySide6.QtCore import QUrl, QTimer
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow
from .service import Service
from .backend import Backend


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument('--no-network', action='store_true')
    parser.add_argument('--data-dir', type=Path)
    parser.add_argument('--smoke-test', action='store_true')
    parser.add_argument('--screenshot', type=Path)
    parser.add_argument('--demo', action='store_true')
    args = parser.parse_args()
    os.environ.setdefault('QT_QUICK_CONTROLS_STYLE', 'Basic')
    app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])
    from .about import load_about
    app_info = load_about(Path(__file__).resolve().parent.parent / 'assets')
    app.setApplicationName(app_info['name'])
    app.setApplicationVersion(app_info['version'])
    app.setDesktopFileName('choroy_reader' if getattr(sys, 'frozen', False) else 'noticias')
    app.setOrganizationName('Choroy Reader')
    project = Path(__file__).resolve().parent.parent
    config_root = Path(os.environ.get('XDG_CONFIG_HOME', Path.home()/'.config'))
    legacy_root = config_root / 'noticias'
    default_root = legacy_root if (legacy_root / 'config.json').is_file() else config_root / 'choroy_reader'
    root = args.data_dir or Path(os.environ.get('CHOROY_READER_DATA_DIR', os.environ.get('MINIMALFEED_DATA_DIR', default_root)))
    service = Service(root, housekeeping=False)
    if args.demo:
        service.config['categorias'] = [{'nombre':'Tecnología', 'sitios':[{'nombre':'Choroy Reader','url':'https://example.com','url_feed':'https://example.com/feed'}]}]
        article = dict(titulo='Choroy Reader: tus fuentes y tu lectura en un mismo lugar', titulo_es='Un lector pensado para leer con calma',
                       link='https://example.com/article', fuente='Choroy Reader', source_url='https://example.com',
                       cuerpo='Este artículo de prueba permite seleccionar texto, destacar varias líneas y buscar palabras.\n\nLa biblioteca conserva los artículos guardados y las descargas permiten leer sin conexión.',
                       estado_contenido='Demostración local', fecha=datetime.now(timezone.utc), traducir_es=True,
                       imagen=(project/'assets/choroy_reader_logo.png').read_bytes())
        service.articles={'https://example.com':[article]}
    backend = Backend(service, project/'assets')
    app.setWindowIcon(QIcon(str(project/'assets/choroy_reader_logo.png')))
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty('backend', backend)
    engine.load(QUrl.fromLocalFile(str(Path(__file__).parent/'qml/main.qml')))
    if not engine.rootObjects():
        return 1
    if not args.demo:
        QTimer.singleShot(0, lambda: backend.startup(allow_network=not args.no_network))
    if args.smoke_test or args.screenshot:
        def finish():
            if args.screenshot:
                window = engine.rootObjects()[0]
                image = window.grabWindow()
                if image.isNull() or not image.save(str(args.screenshot)):
                    app.exit(2)
                    return
            if args.smoke_test:
                app.quit()
        QTimer.singleShot(1500, finish)
    result = app.exec()
    # Destruir los bindings antes que su contexto evita avisos al salir.
    import shiboken6
    for window in engine.rootObjects():
        window.close()
        shiboken6.delete(window)
    shiboken6.delete(engine)
    return result
