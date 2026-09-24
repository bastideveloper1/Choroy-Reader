from pathlib import Path

root = Path(SPECPATH).parent
analysis = Analysis(
    [str(root / 'choroy_reader.py')],
    pathex=[str(root)],
    binaries=[],
    datas=[(str(root / 'choroy_reader/qml'), 'choroy_reader/qml'),
           (str(root / 'assets/choroy_reader_logo.png'), 'assets')],
    hiddenimports=['PySide6.QtQuick', 'PySide6.QtQuickControls2'],
    excludes=['tkinter', 'PyQt5', 'PyQt6'],
)
pyz = PYZ(analysis.pure)
exe = EXE(pyz, analysis.scripts, [], exclude_binaries=True,
          name='choroy_reader', console=False)
app = COLLECT(exe, analysis.binaries, analysis.datas, name='choroy_reader')
