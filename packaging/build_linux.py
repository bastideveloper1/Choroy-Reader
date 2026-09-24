"""Genera un .deb desde la carpeta creada por PyInstaller, sin instalarlo."""
import argparse
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--version', default='0.1.0')
    args = parser.parse_args()
    import re
    if not re.fullmatch(r'[0-9]+(?:\.[0-9]+){2}', args.version):
        parser.error('Usa una versión numérica como 0.1.0')
    arch = {'x86_64': 'amd64', 'aarch64': 'arm64'}.get(platform.machine())
    if platform.system() != 'Linux' or not arch:
        parser.error('Ejecuta este script en Linux x86_64 o aarch64')
    root = Path(__file__).resolve().parent.parent
    bundle = root / 'dist/choroy_reader'
    if not (bundle / 'choroy_reader').is_file():
        parser.error('Primero genera dist/choroy_reader con PyInstaller')
    with tempfile.TemporaryDirectory(prefix='choroy_reader-deb-') as tmp:
        stage = Path(tmp)
        shutil.copytree(bundle, stage / 'opt/choroy_reader')
        for directory in ('DEBIAN', 'usr/bin', 'usr/share/applications', 'usr/share/icons/hicolor/256x256/apps'):
            (stage / directory).mkdir(parents=True, exist_ok=True)
        (stage / 'DEBIAN/control').write_text(
            f'Package: choroy-reader\nVersion: {args.version}\nArchitecture: {arch}\n'
            'Maintainer: Choroy Reader\nSection: net\nPriority: optional\n'
            'Depends: libc6, libgl1, libegl1, libxkbcommon0, libxcb-cursor0, libxcb-icccm4, libxcb-keysyms1, libxcb-shape0, libxcb-xinerama0, libxcb-xkb1, libxkbcommon-x11-0, libfontconfig1, libdbus-1-3\n'
            'Description: Lector de noticias RSS Choroy Reader\n', encoding='utf-8')
        (stage / 'usr/bin/choroy_reader').symlink_to('/opt/choroy_reader/choroy_reader')
        (stage / 'usr/share/applications/choroy_reader.desktop').write_text(
            '[Desktop Entry]\nType=Application\nName=Choroy Reader\n'
            'Comment=Lector de noticias RSS\nExec=choroy_reader\nIcon=choroy_reader\n'
            'Terminal=false\nCategories=Network;News;\n', encoding='utf-8')
        from PIL import Image
        with Image.open(root / 'assets/choroy_reader_logo.png') as image:
            image.thumbnail((256, 256), Image.Resampling.LANCZOS)
            image.save(stage / 'usr/share/icons/hicolor/256x256/apps/choroy_reader.png')
        target = root / f'dist/choroy_reader_{args.version}_{arch}.deb'
        subprocess.run(['dpkg-deb', '--root-owner-group', '--build', str(stage), str(target)], check=True)
        print(target)


if __name__ == '__main__':
    main()
