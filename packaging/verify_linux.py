"""Extract and smoke-test a .deb with synthetic data, without installing it."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from choroy_reader.service import Service


def verify(package, screenshot=None):
    package = Path(package).resolve()
    with tempfile.TemporaryDirectory(prefix='choroy-reader-verify-') as tmp:
        root = Path(tmp)
        install = root / 'installation'
        subprocess.run(['dpkg-deb', '--extract', str(package), str(install)], check=True)
        executable = install / 'opt/choroy_reader/choroy_reader'
        assets = install / 'opt/choroy_reader/_internal/assets'
        info = json.loads((assets / 'app_info.json').read_text())
        package_version = subprocess.check_output(['dpkg-deb', '-f', str(package), 'Version'], text=True).strip()
        assert info['version'] == package_version, 'La versión visible no coincide con la del paquete'
        service = Service(root / 'user-data', housekeeping=False)
        article = dict(link='https://example.com/test', titulo='Prueba de actualización',
                       source_url='https://example.com', fuente='Prueba local',
                       fecha=datetime.now(), cuerpo='Conservar artículo, destacados y notas.')
        service.config.update(categorias=[], color='periodico')
        service.save_config()
        service.library.save('guardados', article)
        service.reader_store.save_original(article['link'], article['cuerpo'])
        service.reader_store.save_marks(article['link'], 'original', article['cuerpo'], [[0, 9, '#ffe88f']])
        note = dict(id='verification-note', position=10, text='Conservar esta nota', color='#a8dcff',
                    theme='gris', html='<p>Conservar esta nota</p>', images=[])
        service.reader_store.save_note(article['link'], 'original', article['cuerpo'], note)
        environment = dict(os.environ, QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software',
                           QT_QUICK_CONTROLS_STYLE='Basic')
        # --data-dir is always explicit: never open the developer's personal library.
        for mode in ('--demo', '--no-network'):
            command = [str(executable), mode, '--data-dir', str(service.root), '--smoke-test']
            if screenshot and mode == '--demo':
                command += ['--screenshot', str(Path(screenshot).resolve())]
            result = subprocess.run(command, cwd=root, env=environment, text=True,
                                    capture_output=True, timeout=45)
            if result.returncode:
                raise RuntimeError(result.stdout + result.stderr)
            if result.stderr.strip():
                print(result.stderr.strip(), file=sys.stderr)
        reopened = Service(service.root, housekeeping=False)
        assert reopened.config['color'] == 'periodico', 'Se perdió la preferencia de tema'
        assert reopened.library.contains('guardados', article['link']), 'Se perdió el artículo guardado'
        assert reopened.reader_store.read(article['link'])['original_marks'] == [[0, 9, '#ffe88f']]
        assert reopened.reader_store.note_record(note['id'])[3] == note, 'Se modificó la nota'
        print(f'OK: paquete {package_version}; arranque empaquetado y conservación de datos de prueba.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package', type=Path)
    parser.add_argument('--screenshot', type=Path)
    args = parser.parse_args()
    verify(args.package, args.screenshot)
