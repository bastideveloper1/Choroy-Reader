from pathlib import Path
import runpy

from PyInstaller.config import CONF

root = Path(SPECPATH).parent
analysis = Analysis(
    [str(root / 'choroy_reader.py')],
    pathex=[str(root)],
    binaries=[],
    datas=[(str(root / 'choroy_reader/qml'), 'choroy_reader/qml'),
           (str(root / 'assets/app_info.json'), 'assets'),
           (str(root / 'assets/noimage.png'), 'assets'),
           (str(root / 'assets/choroy_reader_logo.png'), 'assets')],
    hiddenimports=['PySide6.QtQuick', 'PySide6.QtQuickControls2'],
    excludes=['tkinter', 'PyQt5', 'PyQt6'],
)
# Collect notices from this build, including the native libraries selected above.
notice_dir = Path(CONF['workpath']) / 'runtime-licenses'
collect = runpy.run_path(str(root / 'packaging/collect_notices.py'))['collect']
collect(notice_dir, analysis.binaries)
analysis.datas += [(f'assets/licenses/{path.name}', str(path), 'DATA')
                   for path in sorted(notice_dir.iterdir()) if path.is_file()]
pyz = PYZ(analysis.pure)
exe = EXE(pyz, analysis.scripts, [], exclude_binaries=True,
          name='choroy_reader', console=False)
app = COLLECT(exe, analysis.binaries, analysis.datas, name='choroy_reader')
