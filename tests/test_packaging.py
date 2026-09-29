import hashlib
import importlib.util
import io
import json
import shutil
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('build_linux', ROOT / 'packaging/build_linux.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class PackagingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bundle = self.root / 'bundle'
        assets = self.bundle / '_internal/assets'
        assets.mkdir(parents=True)
        self.info = dict(version='0.1.0', name='Choroy Reader', author='Test', license='Test', repository='https://example.com')
        (assets / 'app_info.json').write_text(json.dumps(self.info))
        for name in ('choroy_reader_logo.png', 'noimage.png'):
            (assets / name).write_bytes(b'fixture')
        (assets / 'licenses').mkdir()
        (assets / 'licenses/manifest.json').write_text('[{"name":"Fixture", "files":["notice.txt"]}]')
        (assets / 'licenses/notice.txt').write_text('Fixture notice')
        qml = self.bundle / '_internal/choroy_reader/qml'
        qml.mkdir(parents=True)
        for name in ('main.qml', 'NoteEditor.qml'):
            (qml / name).write_text('import QtQuick\nItem {}')
        (self.bundle / 'choroy_reader').write_text('#!/bin/sh\nexit 0\n')
        (self.bundle / 'choroy_reader').chmod(0o755)

    def test_rejects_incomplete_bundle_and_private_data(self):
        self.assertEqual(builder.validate_bundle(self.bundle, '0.1.0')['version'], '0.1.0')
        with self.assertRaisesRegex(ValueError, 'versión'):
            builder.validate_bundle(self.bundle, '0.2.0')
        private = self.bundle / '_internal/config.json'
        private.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'datos personales'):
            builder.validate_bundle(self.bundle, '0.1.0')
        private.unlink()
        (self.bundle / '_internal/assets/noimage.png').unlink()
        with self.assertRaisesRegex(ValueError, 'Faltan archivos'):
            builder.validate_bundle(self.bundle, '0.1.0')

    @unittest.skipUnless(shutil.which('dpkg-deb'), 'Debian packaging tools required')
    def test_deb_has_stable_upgrade_paths_and_checksum_without_user_data(self):
        versions = ('0.1.0', '0.1.1')
        payloads = []
        for version in versions:
            self.info['version'] = version
            (self.bundle / '_internal/assets/app_info.json').write_text(json.dumps(self.info))
            target = self.root / f'choroy-reader_{version}_amd64.deb'
            builder.build_package(ROOT, self.bundle, version, 'amd64', target)
            fields = subprocess.check_output(['dpkg-deb', '-f', str(target), 'Package', 'Version', 'Depends'], text=True)
            self.assertIn('Package: choroy-reader', fields)
            self.assertIn('Version: ' + version, fields)
            self.assertIn('libc6 (>= ', fields)
            raw = subprocess.check_output(['dpkg-deb', '--fsys-tarfile', str(target)])
            with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
                names = archive.getnames()
                self.assertTrue(all(name == '.' or name.startswith(('./opt/', './usr/')) or name in ('./opt', './usr') for name in names))
                launcher = archive.getmember('./usr/bin/choroy_reader')
                self.assertTrue(launcher.issym())
                self.assertEqual(launcher.linkname, '/opt/choroy_reader/choroy_reader')
                self.assertTrue(all(entry.uid == entry.gid == 0 for entry in archive.getmembers()))
                payloads.append(names)
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
            self.assertEqual(target.with_suffix('.deb.sha256').read_text(), f'{digest}  {target.name}\n')
        self.assertEqual(payloads[0], payloads[1])
        subprocess.run(['dpkg', '--compare-versions', versions[0], 'lt', versions[1]], check=True)
