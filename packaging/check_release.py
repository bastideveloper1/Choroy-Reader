"""Run release tests; isolate Qt engines to avoid cumulative native teardown crashes."""
import ast
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent


def main():
    environment = dict(os.environ, QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software',
                       QT_QUICK_CONTROLS_STYLE='Basic')
    failures = []
    count = 0
    for path in sorted((ROOT / 'tests').glob('test_*.py')):
        cases = [None]
        if path.name == 'test_qt.py':
            cases = [node.name for node in ast.walk(ast.parse(path.read_text(encoding='utf-8')))
                     if isinstance(node, ast.FunctionDef) and node.name.startswith('test_')]
        for case in cases:
            name = path.name + (':' + case if case else '')
            command = [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', path.name]
            if case:
                command += ['-k', case]
            try:
                result = subprocess.run(command, cwd=ROOT, env=environment, capture_output=True,
                                        text=True, timeout=120)
                if result.returncode:
                    failures.append(name)
                    print(result.stdout + result.stderr, flush=True)
                print(('OK ' if not result.returncode else 'FAIL ') + name, flush=True)
            except subprocess.TimeoutExpired:
                failures.append(name)
                print('TIMEOUT ' + name, flush=True)
            count += 1
    print(f'{count} ejecuciones; {len(failures)} fallos: {failures}', flush=True)
    return bool(failures)


if __name__ == '__main__':
    sys.exit(main())
