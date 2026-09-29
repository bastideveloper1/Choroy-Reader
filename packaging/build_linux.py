"""Build an upgradeable .deb from PyInstaller output, without installing it."""
import argparse
import hashlib
import json
import platform
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

REQUIRED_ASSETS = ('app_info.json', 'choroy_reader_logo.png', 'noimage.png', 'licenses/manifest.json')
DEPENDENCIES = ('libgl1', 'libegl1', 'libxkbcommon0', 'libxcb-cursor0', 'libxcb-icccm4',
                'libxcb-keysyms1', 'libxcb-shape0', 'libxcb-xinerama0', 'libxcb-xkb1',
                'libxkbcommon-x11-0', 'libfontconfig1', 'libdbus-1-3', 'fonts-dejavu-core')


def validate_bundle(bundle, version):
    bundle = Path(bundle)
    if not (bundle / 'choroy_reader').is_file():
        raise ValueError('Primero genera dist/choroy_reader con PyInstaller')
    internal = bundle / '_internal'
    required = [internal / 'assets' / name for name in REQUIRED_ASSETS]
    required += [internal / 'choroy_reader/qml' / name for name in ('main.qml', 'NoteEditor.qml')]
    missing = [str(path.relative_to(bundle)) for path in required if not path.is_file()]
    if missing:
        raise ValueError('Faltan archivos del programa: ' + ', '.join(missing))
    info = json.loads((internal / 'assets/app_info.json').read_text(encoding='utf-8'))
    if info['version'] != version:
        raise ValueError('La versión del paquete debe coincidir con assets/app_info.json del ejecutable')
    for path in bundle.rglob('*'):
        if path.name in {'config.json', 'biblioteca', 'favicons', '.git', '.venv'} or path.name.startswith('reader_state.sqlite3'):
            raise ValueError('El ejecutable contiene datos personales: ' + str(path.relative_to(bundle)))
    notices = json.loads((internal / 'assets/licenses/manifest.json').read_text(encoding='utf-8'))
    if not notices:
        raise ValueError('No hay avisos de dependencias en el ejecutable')
    for notice in notices:
        for name in notice.get('files', []):
            if Path(name).name != name or not (internal / 'assets/licenses' / name).is_file():
                raise ValueError('Falta un aviso de licencia: ' + name)
    return info


def build_package(root, bundle, version, arch, target):
    root, bundle, target = Path(root), Path(bundle), Path(target)
    info = validate_bundle(bundle, version)
    libc, libc_version = platform.libc_ver()
    if libc != 'glibc' or not re.fullmatch(r'[0-9]+\.[0-9]+', libc_version):
        raise ValueError('Construye el paquete en un sistema Linux con glibc')
    with tempfile.TemporaryDirectory(prefix='choroy_reader-deb-') as tmp:
        stage = Path(tmp)
        shutil.copytree(bundle, stage / 'opt/choroy_reader', symlinks=True)
        for directory in ('DEBIAN', 'usr/bin', 'usr/share/applications',
                          'usr/share/doc/choroy-reader', 'usr/share/icons/hicolor/256x256/apps'):
            (stage / directory).mkdir(parents=True, exist_ok=True)
        installed_size = sum(path.stat().st_size for path in (stage / 'opt').rglob('*')
                             if path.is_file() and not path.is_symlink()) // 1024
        dependencies = ', '.join((f'libc6 (>= {libc_version})', *DEPENDENCIES))
        (stage / 'DEBIAN/control').write_text(
            f'Package: choroy-reader\nVersion: {version}\nArchitecture: {arch}\n'
            f'Maintainer: {info["author"]}\nSection: net\nPriority: optional\n'
            f'Installed-Size: {installed_size}\nHomepage: {info["repository"]}\n'
            f'Depends: {dependencies}\n'
            'Description: Lector de noticias RSS Choroy Reader\n'
            ' Lectura sin conexión, traducciones, destacados y notas con imágenes.\n', encoding='utf-8')
        (stage / 'usr/bin/choroy_reader').symlink_to('/opt/choroy_reader/choroy_reader')
        (stage / 'usr/share/applications/choroy_reader.desktop').write_text(
            '[Desktop Entry]\nType=Application\nName=Choroy Reader\n'
            'Comment=Lector de noticias RSS\nExec=choroy_reader\nTryExec=choroy_reader\nIcon=choroy_reader\n'
            'Terminal=false\nCategories=Network;News;\nStartupNotify=true\n', encoding='utf-8')
        (stage / 'usr/share/doc/choroy-reader/copyright').write_text(
            f'{info["name"]} {version}\nAutor: {info["author"]}\n'
            f'Licencia de la aplicación: {info["license"]}\n\n'
            'Los avisos y licencias de los componentes incluidos están en\n'
            '/opt/choroy_reader/_internal/assets/licenses/ y en Acerca de.\n', encoding='utf-8')
        (stage / 'usr/share/doc/choroy-reader/README').write_text(
            'Para actualizar, cierra Choroy Reader e instala un .deb de versión superior.\n'
            'El paquete reemplaza el programa en /opt/choroy_reader.\n'
            'No incluye ni reemplaza datos de usuario en ~/.config/noticias o\n'
            '~/.config/choroy_reader. Desinstalar tampoco elimina esos datos.\n'
            'No se configura un repositorio de actualizaciones automáticamente.\n', encoding='utf-8')
        from PIL import Image
        with Image.open(root / 'assets/choroy_reader_logo.png') as image:
            image.thumbnail((256, 256), Image.Resampling.LANCZOS)
            image.save(stage / 'usr/share/icons/hicolor/256x256/apps/choroy_reader.png')
        target.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(['dpkg-deb', '--root-owner-group', '-Zxz', '-z6', '--build', str(stage), str(target)], check=True)
    with target.open('rb') as artifact:
        checksum = hashlib.file_digest(artifact, 'sha256').hexdigest()
    target.with_suffix(target.suffix + '.sha256').write_text(f'{checksum}  {target.name}\n', encoding='utf-8')
    return target


def main():
    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', default=json.loads((root / 'assets/app_info.json').read_text())['version'])
    args = parser.parse_args()
    if not re.fullmatch(r'[0-9]+(?:\.[0-9]+){2}', args.version):
        parser.error('Usa una versión numérica como 0.1.0')
    arch = {'x86_64': 'amd64', 'aarch64': 'arm64'}.get(platform.machine())
    if platform.system() != 'Linux' or not arch:
        parser.error('Ejecuta este script en Linux x86_64 o aarch64')
    try:
        target = build_package(root, root / 'dist/choroy_reader', args.version, arch,
                               root / f'dist/choroy_reader_{args.version}_{arch}.deb')
    except ValueError as error:
        parser.error(str(error))
    print(target)


if __name__ == '__main__':
    main()
