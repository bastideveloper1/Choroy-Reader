"""OPML exchange and versioned local backups; never archives application code."""
import copy
import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

from . import core

DATA = ('config.json', 'reader_state.sqlite3', 'biblioteca', 'cache', 'portable_icons')
COLLECTIONS = {'feed', 'historial', 'retirados', 'guardados', 'descargas', 'archivados'}
NS = 'https://choroy-reader.local/opml'
ET.register_namespace('choroy', NS)


def web_url(value):
    parsed = urlparse(value)
    return parsed.scheme in {'http', 'https'} and bool(parsed.netloc)


def atomic_write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(data)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def export_opml(config, path):
    root = ET.Element('opml', version='2.0')
    ET.SubElement(ET.SubElement(root, 'head'), 'title').text = 'Choroy Reader'
    body = ET.SubElement(root, 'body')
    for category in config['categorias']:
        group = ET.SubElement(body, 'outline', text=category['nombre'])
        for source in category['sitios']:
            attrs = dict(text=source['nombre'], title=source['nombre'], htmlUrl=source['url'])
            feed = source.get('url_feed')
            shortcut = source.get('source_type') == 'shortcut'
            if feed and not shortcut:
                attrs.update(type='rss', xmlUrl=feed)
            else:
                attrs.update(type='link', url=source['url'])
            attrs['{' + NS + '}sourceType'] = 'shortcut' if shortcut else 'feed'
            attrs['{' + NS + '}showShortcut'] = str(source.get('show_shortcut', shortcut)).lower()
            ET.SubElement(group, 'outline', attrs)
    ET.indent(root)
    atomic_write(path, ET.tostring(root, encoding='utf-8', xml_declaration=True))


def import_opml(config, path):
    data = Path(path).read_bytes()
    if len(data) > 10 * 1024 * 1024 or b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
        raise ValueError('OPML demasiado grande o con declaraciones no permitidas')
    root = ET.fromstring(data)
    if root.tag != 'opml' or root.find('body') is None:
        raise ValueError('El archivo no es un OPML válido')
    result = copy.deepcopy(config)
    added = skipped = 0
    def visit(parent, names, depth=0):
        nonlocal added, skipped
        if depth > 30:
            raise ValueError('El OPML tiene demasiados niveles de categorías')
        for node in parent.findall('outline'):
            feed = node.get('xmlUrl', '').strip()
            url = (node.get('htmlUrl') or node.get('url') or feed).strip()
            name = node.get('text') or node.get('title') or url or 'Importadas'
            if url:
                if not web_url(url) or (feed and not web_url(feed)):
                    skipped += 1
                    continue
                category_name = ' / '.join(names) or 'Importadas'
                category = next((c for c in result['categorias'] if c['nombre'] == category_name), None)
                if category is None:
                    category = dict(nombre=category_name, sitios=[])
                    result['categorias'].append(category)
                if any(s['url'].rstrip('/') == url.rstrip('/') or (feed and s.get('url_feed') == feed) for s in category['sitios']):
                    skipped += 1
                    continue
                source = core.source_defaults(name, url)
                source['url_feed'] = feed or None
                source['source_type'] = node.get('{' + NS + '}sourceType') or ('feed' if feed else 'shortcut')
                if source['source_type'] not in {'feed', 'shortcut'}:
                    source['source_type'] = 'feed' if feed else 'shortcut'
                source['show_shortcut'] = node.get('{' + NS + '}showShortcut', str(source['source_type'] == 'shortcut')).lower() == 'true'
                category['sitios'].append(source)
                added += 1
            else:
                # Keep empty categories as well as nested groups.
                group_name = ' / '.join([*names, name])
                if not node.findall('outline') and not any(c['nombre'] == group_name for c in result['categorias']):
                    result['categorias'].append(dict(nombre=group_name, sitios=[]))
                visit(node, [*names, name], depth + 1)
    visit(root.find('body'), [])
    return result, added, skipped


def safe_target(root, target):
    target = Path(target).resolve()
    for name in DATA:
        managed = (Path(root) / name).resolve()
        if target == managed or managed in target.parents:
            raise ValueError('Elige un destino fuera de los archivos de datos de la aplicación')
    return target


def create_backup(service, target):
    target = safe_target(service.root, target)
    service.save_config()
    with tempfile.TemporaryDirectory(prefix='choroy-backup-') as temp:
        stage = Path(temp)
        for name in DATA:
            source = service.root / name
            if source.is_symlink():
                raise ValueError('No se pueden respaldar carpetas de datos enlazadas')
            if source.is_dir():
                shutil.copytree(source, stage / name, ignore=lambda folder, names: [n for n in names if (Path(folder) / n).is_symlink()])
        config = copy.deepcopy(service.config)
        for category in config['categorias']:
            for source in category['sitios']:
                custom = source.get('favicon_personalizado')
                if not custom:
                    continue
                icon = Path(custom)
                if icon.is_file():
                    relative = 'portable_icons/' + hashlib.sha256(icon.read_bytes()).hexdigest() + icon.suffix
                    (stage / 'portable_icons').mkdir(exist_ok=True)
                    shutil.copyfile(icon, stage / relative)
                    source['favicon_personalizado'] = relative
                else:
                    source['favicon_personalizado'] = None
        (stage / 'config.json').write_text(json.dumps(config, ensure_ascii=False), encoding='utf-8')
        with sqlite3.connect(service.reader_store.path) as original, sqlite3.connect(stage / 'reader_state.sqlite3') as snapshot:
            original.backup(snapshot)
        files = {p.relative_to(stage).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in stage.rglob('*') if p.is_file()}
        manifest = dict(format='choroy-reader-backup', version=1, created=datetime.now(timezone.utc).isoformat(), files=files)
        (stage / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=target.parent, suffix='.zip', delete=False) as stream:
            temporary = Path(stream.name)
        try:
            with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as archive:
                for file in stage.rglob('*'):
                    if file.is_file():
                        archive.write(file, file.relative_to(stage).as_posix())
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)


def validate_backup(path, stage):
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or len(names) > 200000 or sum(i.file_size for i in archive.infolist()) > 4 * 1024**3:
            raise ValueError('Copia duplicada o demasiado grande')
        for name in names:
            part = PurePosixPath(name)
            if part.is_absolute() or '..' in part.parts or '\\' in name or not part.parts or part.parts[0] not in {*DATA, 'manifest.json'}:
                raise ValueError('La copia contiene una ruta no permitida')
        manifest = json.loads(archive.read('manifest.json'))
        if manifest.get('format') != 'choroy-reader-backup' or manifest.get('version') != 1:
            raise ValueError('Formato o versión de copia no compatible')
        files = manifest.get('files', {})
        if set(names) != {*files, 'manifest.json'} or not {'config.json', 'reader_state.sqlite3'} <= set(files):
            raise ValueError('Copia incompleta')
        for name, digest in files.items():
            data = archive.read(name)
            if hashlib.sha256(data).hexdigest() != digest:
                raise ValueError('La copia está dañada: ' + name)
            destination = stage / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
    config = json.loads((stage / 'config.json').read_text(encoding='utf-8'))
    if not isinstance(config, dict) or not isinstance(config.get('categorias'), list):
        raise ValueError('Configuración inválida')
    for category in config['categorias']:
        if not isinstance(category.get('nombre'), str) or not isinstance(category.get('sitios'), list):
            raise ValueError('Categoría inválida')
        for source in category['sitios']:
            if not isinstance(source.get('nombre'), str) or not isinstance(source.get('url'), str):
                raise ValueError('Fuente inválida')
            icon = source.get('favicon_personalizado')
            if icon and (icon not in files or not icon.startswith('portable_icons/')):
                raise ValueError('Icono fuera de la copia')
    from .library import Library
    library = Library(stage / 'biblioteca')
    for name in files:
        if name.startswith('biblioteca/'):
            parts = PurePosixPath(name).parts
            if len(parts) != 3 or parts[1] not in COLLECTIONS:
                raise ValueError('Colección desconocida')
            article = library.read_path(stage / name)
            if not isinstance(article.get('link'), str) or library.path(parts[1], article['link']).name != parts[2]:
                raise ValueError('Artículo inválido')
    with sqlite3.connect(stage / 'reader_state.sqlite3') as db:
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('Base de datos dañada')
        db.execute('SELECT link, original, translation, original_marks, translated_marks FROM reader_state LIMIT 1')
    return config


def restore_backup(service, path):
    root = service.root
    # Stage and validate everything before changing current data.
    with tempfile.TemporaryDirectory(prefix='.restore-', dir=root) as temp:
        stage = Path(temp) / 'incoming'
        stage.mkdir()
        config = validate_backup(path, stage)
        for category in config['categorias']:
            for source in category['sitios']:
                icon = source.get('favicon_personalizado')
                if icon:
                    source['favicon_personalizado'] = str(root / icon)
        (stage / 'config.json').write_text(json.dumps(config, ensure_ascii=False), encoding='utf-8')
        from .service import Service
        Service(stage, housekeeping=False)  # Validate runtime loading before replacement.
        recovery = root / 'backups' / ('antes-de-restaurar-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.zip')
        create_backup(service, recovery)
        rollback = Path(temp) / 'previous'
        rollback.mkdir()
        moved, installed = [], []
        try:
            for name in DATA:
                destination = root / name
                if destination.exists():
                    os.replace(destination, rollback / name)
                    moved.append(name)
                if (stage / name).exists():
                    os.replace(stage / name, destination)
                    installed.append(name)
            restored = Service(root, housekeeping=False)
        except Exception:
            for name in reversed(installed):
                item = root / name
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
            for name in moved:
                os.replace(rollback / name, root / name)
            raise
    return restored, recovery
