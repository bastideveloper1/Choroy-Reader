import copy
import json
import tempfile
import unittest
import zipfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from choroy_reader.service import Service
from choroy_reader import portability


class PortabilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.service = Service(self.root / 'original')
        self.service.config['categorias'] = [dict(nombre='Tecnología & ciencia', sitios=[
            dict(nombre='Fuente', url='https://example.com', url_feed='https://example.com/rss', source_type='feed', show_shortcut=True),
            dict(nombre='Atajo', url='https://shortcut.example', source_type='shortcut', show_shortcut=True),
        ]), dict(nombre='Vacía', sitios=[])]
        self.article = dict(link='https://example.com/a', titulo='Título', source_url='https://example.com',
                            fecha=datetime.now(), cuerpo='Texto completo del artículo', imagen=b'imagen')

    def tearDown(self):
        self.tmp.cleanup()

    def test_opml_roundtrip_merge_and_duplicate_protection(self):
        path = self.root / 'sources.opml'
        portability.export_opml(self.service.config, path)
        config, added, skipped = portability.import_opml({'categorias': [], 'color': 'periodico'}, path)
        self.assertEqual((added, skipped), (2, 0))
        self.assertEqual(config['color'], 'periodico')
        self.assertEqual(config['categorias'][0]['nombre'], 'Tecnología & ciencia')
        self.assertEqual(config['categorias'][1], dict(nombre='Vacía', sitios=[]))
        feed, shortcut = config['categorias'][0]['sitios']
        self.assertEqual(feed['url_feed'], 'https://example.com/rss')
        self.assertTrue(feed['show_shortcut'])
        self.assertEqual(shortcut['source_type'], 'shortcut')
        again, added, skipped = portability.import_opml(config, path)
        self.assertEqual((added, skipped), (0, 2))
        self.assertEqual(config, again)

    def test_external_opml_nested_categories_and_invalid_urls(self):
        path = self.root / 'external.opml'
        path.write_text('<opml version="2.0"><body><outline text="A"><outline text="B"><outline text="Feed" type="rss" xmlUrl="https://example.com/rss"/></outline></outline><outline text="Bad" xmlUrl="file:///tmp/private"/></body></opml>')
        config, added, skipped = portability.import_opml({'categorias': []}, path)
        self.assertEqual((added, skipped), (1, 1))
        self.assertEqual(config['categorias'][0]['nombre'], 'A / B')
        self.assertEqual(config['categorias'][0]['sitios'][0]['source_type'], 'feed')
        path.write_text('<!DOCTYPE opml [<!ENTITY x "test">]><opml><body/></opml>')
        with self.assertRaises(ValueError):
            portability.import_opml(config, path)

    def populate(self):
        for kind in portability.COLLECTIONS:
            self.service.library.save(kind, self.article)
        self.service.seen.add(self.article['link'])
        self.service.dismissed.add(self.article['link'])
        self.service.config.update(color='periodico', historial_dias=7, progreso_lectura={self.article['link']: {'original': {'position': 3, 'percent': 12}}})
        self.service.reader_store.save_original(self.article['link'], self.article['cuerpo'])
        self.service.reader_store.save_translation(self.article['link'], self.article['cuerpo'], 'Translated text')
        self.service.reader_store.save_marks(self.article['link'], 'original', self.article['cuerpo'], [(0, 5, '#ffe88f')])
        self.service.lifecycle.remember(self.article['link'], 1)
        icon = self.root / 'custom.png'
        icon.write_bytes(b'custom-icon')
        self.service.config['categorias'][0]['sitios'][0]['favicon_personalizado'] = str(icon)
        self.service.save_config()

    def test_backup_restores_all_data_into_another_directory(self):
        self.populate()
        target = self.root / 'backup.zip'
        portability.create_backup(self.service, target)
        (self.root / 'custom.png').unlink()
        other = Service(self.root / 'other')
        other.config['categorias'] = []
        other.save_config()
        extra = dict(self.article, link='https://example.com/extra')
        other.library.save('guardados', extra)
        sentinel = other.root / 'noticias.py'
        sentinel.write_text('application code remains')
        restored, recovery = portability.restore_backup(other, target)
        self.assertTrue(recovery.exists())
        self.assertEqual(sentinel.read_text(), 'application code remains')
        for kind in portability.COLLECTIONS:
            self.assertEqual(len(restored.library.list_items(kind)), 1)
        self.assertEqual(restored.seen, self.service.seen)
        self.assertEqual(restored.dismissed, self.service.dismissed)
        self.assertEqual(restored.config['color'], 'periodico')
        self.assertEqual(restored.config['progreso_lectura'], self.service.config['progreso_lectura'])
        self.assertEqual(restored.reader_store.read(self.article['link'])['original_marks'], [[0, 5, '#ffe88f']])
        self.assertEqual(restored.reader_store.read(self.article['link'])['translation'], 'Translated text')
        custom = Path(restored.config['categorias'][0]['sitios'][0]['favicon_personalizado'])
        self.assertTrue(custom.is_relative_to(restored.root))
        self.assertEqual(custom.read_bytes(), b'custom-icon')
        # The automatic pre-restore snapshot is itself usable.
        previous, _ = portability.restore_backup(restored, recovery)
        self.assertEqual(previous.config['categorias'], [])
        self.assertTrue(previous.library.contains('guardados', extra['link']))

    def test_corrupt_or_unsafe_backup_does_not_change_data(self):
        self.populate()
        target = self.root / 'backup.zip'
        portability.create_backup(self.service, target)
        before = self.service.config_path.read_bytes()
        for name, value in [('config.json', b'{}'), ('../escape', b'bad')]:
            corrupt = self.root / 'corrupt.zip'
            with zipfile.ZipFile(target) as original, zipfile.ZipFile(corrupt, 'w') as archive:
                for entry in original.namelist():
                    archive.writestr(entry, value if entry == name else original.read(entry))
                if name not in original.namelist():
                    archive.writestr(name, value)
            with self.assertRaises(ValueError):
                portability.restore_backup(self.service, corrupt)
            self.assertEqual(self.service.config_path.read_bytes(), before)
        self.assertFalse((self.root / 'escape').exists())

    def test_restore_rolls_back_when_replacement_fails(self):
        self.populate()
        target = self.root / 'backup.zip'
        portability.create_backup(self.service, target)
        self.service.config['color'] = 'azul_neon'
        self.service.save_config()
        before = self.service.config_path.read_bytes()
        real_replace = portability.os.replace
        def fail_once(source, destination):
            if Path(source).parent.name == 'incoming' and Path(source).name == 'biblioteca':
                raise OSError('Simulated replacement failure')
            return real_replace(source, destination)
        with patch.object(portability.os, 'replace', side_effect=fail_once):
            with self.assertRaises(OSError):
                portability.restore_backup(self.service, target)
        self.assertEqual(self.service.config_path.read_bytes(), before)
        self.assertTrue(self.service.library.contains('guardados', self.article['link']))

    def test_backup_cannot_overwrite_managed_data(self):
        with self.assertRaises(ValueError):
            portability.create_backup(self.service, self.service.config_path)


if __name__ == '__main__':
    unittest.main()
