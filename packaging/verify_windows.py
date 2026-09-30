"""Smoke-test a Windows bundle or installed executable using only synthetic data."""
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


def verify(executable, screenshot=None):
    executable = Path(executable).resolve()
    bundle = executable.parent
    info = json.loads((bundle / '_internal/assets/app_info.json').read_text(encoding='utf-8'))
    expected = json.loads((ROOT / 'assets/app_info.json').read_text(encoding='utf-8'))['version']
    assert info['version'] == expected
    assert (bundle / '_internal/assets/fonts/DejaVuSans.ttf').is_file()
    for path in bundle.rglob('*'):
        assert path.name not in {'config.json', 'biblioteca', 'favicons', '.git', '.venv'}, str(path)
        assert not path.name.startswith('reader_state.sqlite3'), str(path)
    with tempfile.TemporaryDirectory(prefix='choroy-windows-verify-') as temporary:
        root = Path(temporary)
        service = Service(root / 'data', housekeeping=False)
        service.config.update(categorias=[], color='periodico')
        service.save_config()
        article = dict(link='https://example.com/verification', titulo='Noticia de prueba',
                       fecha=datetime.now(), cuerpo='Conservar notas y destacados.')
        service.library.save('guardados', article)
        service.reader_store.save_original(article['link'], article['cuerpo'])
        service.reader_store.save_marks(article['link'], 'original', article['cuerpo'], [[0, 9, '#ffe88f']])
        note = dict(id='verification-note', position=0, text='Mi nota', color='#ffe88f', images=[])
        service.reader_store.save_note(article['link'], 'original', article['cuerpo'], note)
        environment = dict(os.environ, QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software',
                           QT_QUICK_CONTROLS_STYLE='Basic')
        for mode in ('--demo', '--no-network'):
            command = [str(executable), mode, '--data-dir', str(service.root), '--smoke-test']
            if screenshot and mode == '--demo':
                command += ['--screenshot', str(Path(screenshot).resolve())]
            subprocess.run(command, cwd=root, env=environment, check=True, timeout=60)
        reopened = Service(service.root, housekeeping=False)
        assert reopened.config['color'] == 'periodico'
        assert reopened.library.contains('guardados', article['link'])
        assert reopened.reader_store.read(article['link'])['original_marks'] == [[0, 9, '#ffe88f']]
        assert reopened.reader_store.note_record(note['id'])[3] == note
        service.search_index.close()
        reopened.search_index.close()
    print(f'OK: Windows {expected}; arranque y conservación de biblioteca, notas y destacados.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('executable', type=Path)
    parser.add_argument('--screenshot', type=Path)
    args = parser.parse_args()
    verify(args.executable, args.screenshot)
