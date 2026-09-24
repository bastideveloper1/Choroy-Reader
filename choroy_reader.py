"""Punto de entrada de Choroy Reader (PySide6 + Qt Quick/QML)."""
import importlib.util
import os
import sys
from pathlib import Path


def main():
    if importlib.util.find_spec('PySide6') is None:
        python = Path(__file__).resolve().parent / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
        if python.exists() and Path(sys.executable).absolute() != python.absolute():
            os.execv(str(python), [str(python), str(Path(__file__).resolve()), *sys.argv[1:]])
        raise SystemExit('Instala las dependencias con: python -m pip install -r requirements.txt')
    from choroy_reader.app import run
    return run()


if __name__ == '__main__':
    sys.exit(main())
