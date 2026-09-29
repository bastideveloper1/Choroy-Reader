"""Collect installed runtime license texts; regenerate in each build environment."""
import argparse
import importlib.metadata as metadata
import json
import platform
import shutil
import sqlite3
import sysconfig
from pathlib import Path

PACKAGES = {
    'PySide6': ('python3-pyside6', 'https://doc.qt.io/qtforpython-6/licenses.html'),
    'PySide6_Essentials': ('python3-pyside6', 'https://doc.qt.io/qtforpython-6/licenses.html'),
    'PySide6_Addons': ('python3-pyside6', 'https://doc.qt.io/qtforpython-6/licenses.html'),
    'shiboken6': ('python3-shiboken6', 'https://doc.qt.io/qtforpython-6/licenses.html'),
    'Pillow': ('python3-pil', 'https://github.com/python-pillow/Pillow'),
    'beautifulsoup4': ('python3-bs4', 'https://www.crummy.com/software/BeautifulSoup/'),
    'soupsieve': ('python3-soupsieve', 'https://github.com/facelessuser/soupsieve'),
    'typing_extensions': ('python3-typing-extensions', 'https://github.com/python/typing_extensions'),
}


def collect(output, bundled_binaries=()):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    result = []
    for package, (debian, url) in PACKAGES.items():
        try:
            dist = metadata.distribution(package)
        except metadata.PackageNotFoundError:
            continue
        files = []
        candidates = [Path(dist.locate_file(f)) for f in dist.files or []
                      if any(piece.lower().startswith(('license', 'copying', 'copyright', 'notice')) for piece in Path(f).parts)
                      and Path(dist.locate_file(f)).is_file()]
        if not candidates:
            fallback = Path('/usr/share/doc') / debian / 'copyright'
            if fallback.is_file():
                candidates = [fallback]
        for i, path in enumerate(candidates):
            try:
                text = path.read_text(encoding='utf-8')
            except UnicodeError:
                continue
            name = f'{package}-{i}-{path.name}.txt'
            (output / name).write_text(text, encoding='utf-8')
            files.append(name)
        license_name = dist.metadata.get('License-Expression') or dist.metadata.get('License') or 'Ver avisos incluidos'
        if package.lower().startswith(('pyside', 'shiboken')):
            for name in ('LGPL-3.0.txt', 'GPL-2.0.txt', 'GPL-3.0.txt'):
                shutil.copyfile(Path(__file__).resolve().parent.parent / 'assets/licenses' / name, output / name) if (Path(__file__).resolve().parent.parent / 'assets/licenses' / name).resolve() != (output / name).resolve() else None
                if name not in files:
                    files.append(name)
        if not files:
            raise RuntimeError(f'No se encontraron textos de licencia para {package}; añádelos antes de distribuir.')
        result.append(dict(name=package, version=dist.version, license=license_name, url=url, files=files))
    python_license = Path(sysconfig.get_path('stdlib')) / 'LICENSE.txt'
    if not python_license.exists():
        python_license = Path(sysconfig.get_config_var('prefix')) / 'LICENSE.txt'
    if not python_license.is_file():
        raise RuntimeError('No se encontró la licencia del intérprete Python')
    shutil.copyfile(python_license, output / 'Python.txt')
    result.append(dict(name='Python', version=platform.python_version(), license='PSF y avisos de terceros', url='https://docs.python.org/3/license.html', files=['Python.txt']))
    from PySide6.QtCore import qVersion
    result.append(dict(name='Qt', version=qVersion(), license='LGPL-3.0 / GPL; véanse los módulos distribuidos', url='https://doc.qt.io/qt-6/licenses-used-in-qt.html', files=['LGPL-3.0.txt', 'GPL-3.0.txt']))
    # SQLite copyright is included in Debian's package notice when available.
    sqlite_notice = Path('/usr/share/doc/libsqlite3-0/copyright')
    if sqlite_notice.exists():
        shutil.copyfile(sqlite_notice, output / 'SQLite.txt')
        result.append(dict(name='SQLite', version=sqlite3.sqlite_version, license='Dominio público; ver aviso', url='https://www.sqlite.org/copyright.html', files=['SQLite.txt']))
    # Collect native-library notices for libraries actually selected by PyInstaller.
    if bundled_binaries and platform.system() == 'Linux':
        import subprocess
        owners = set()
        sources = sorted({source for _, source, *_ in bundled_binaries
                          if source.startswith(('/usr/lib/', '/lib/'))})
        # One package-database scan per batch instead of one per shared library.
        for offset in range(0, len(sources), 64):
            found = subprocess.run(['dpkg-query', '-S', *sources[offset:offset + 64]],
                                   capture_output=True, text=True)
            owners.update(line.split(': ', 1)[0] for line in found.stdout.splitlines() if ': ' in line)
        for owner in sorted(owners):
            package = owner.split(':')[0]
            notice = Path('/usr/share/doc') / package / 'copyright'
            if notice.is_file():
                name = 'native-' + package + '.txt'
                shutil.copyfile(notice, output / name)
                version = subprocess.run(['dpkg-query', '-W', '-f=${Version}', owner], capture_output=True, text=True).stdout
                result.append(dict(name=package, version=version, license='Ver avisos incluidos', url='', files=[name]))
    (output / 'manifest.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parent.parent / 'assets/licenses')
    args = parser.parse_args()
    collect(args.output)
