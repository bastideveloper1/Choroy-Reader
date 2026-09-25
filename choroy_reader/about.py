"""Local application identity and dependency notices, also available offline."""
import json
from pathlib import Path


def load_about(assets):
    assets = Path(assets)
    info = json.loads((assets / 'app_info.json').read_text(encoding='utf-8'))
    notices = assets / 'licenses' / 'manifest.json'
    info['dependencies'] = json.loads(notices.read_text(encoding='utf-8')) if notices.exists() else []
    license_file = info.get('license_file')
    info['license_text'] = (assets / license_file).read_text(encoding='utf-8') if license_file else ''
    return info


def notice_text(assets, dependency):
    root = (Path(assets) / 'licenses').resolve()
    parts = []
    for name in dependency.get('files', []):
        path = (root / name).resolve()
        if path.parent != root:
            raise ValueError('Ruta de licencia inválida')
        parts.append(name + '\n\n' + path.read_text(encoding='utf-8'))
    return '\n\n'.join(parts)
