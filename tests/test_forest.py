import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from choroy_reader.service import Service
from choroy_reader.forest import Forest
from choroy_reader import portability


class ForestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.service = Service(Path(self.tmp.name) / 'data', housekeeping=False)
        self.service.config['categorias'] = [dict(nombre='Test', sitios=[dict(nombre='Fuente', url='https://example.org')])]
        self.article = dict(link='https://example.org/a', source_url='https://example.org', titulo='Energía solar', cuerpo='Energía solar', fecha=datetime.now())

    def test_months_deduplication_and_persistence(self):
        forest = self.service.forest
        for month in (1, 1, 2):
            forest.record(self.article, 'received', datetime(2026, month, 1))
            forest.record(self.article, 'opened', datetime(2026, month, 1))
        forest = Forest(self.service.reader_store)
        report = forest.report(self.service.config['categorias'])
        self.assertEqual(report['rows'][0]['received'], 1)
        self.assertEqual(report['rows'][0]['opened'], 1)
        feb = forest.report(self.service.config['categorias'], '2026-02')['rows'][0]
        self.assertEqual(feb['received'], 0)
        self.assertEqual(feb['opened'], 1)

    def test_review_expiry_and_reset(self):
        forest = self.service.forest
        url = self.article['source_url']
        forest.review(url, 'later')
        self.assertEqual(forest.report(self.service.config['categorias'])['pending'], 0)
        with self.service.reader_store.connect() as db:
            db.execute("UPDATE forest_reviews SET until='2000-01-01'")
        self.assertEqual(forest.report(self.service.config['categorias'])['pending'], 1)
        forest.review(url, 'keep')
        forest.review(url, 'reset')
        self.assertEqual(forest.report(self.service.config['categorias'])['pending'], 1)

    def test_refresh_radar_and_backup(self):
        self.service.config['radar_palabras'] = ['solar']
        other = dict(self.article, link='https://example.org/b', titulo='Otro tema', cuerpo='Cocina')
        self.service.apply_refresh(({self.article['source_url']: [self.article, other]}, {}, []))
        row = self.service.forest.report(self.service.config['categorias'])['rows'][0]
        self.assertEqual((row['received'], row['evaluated'], row['matched']), (2, 2, 1))
        self.assertEqual(row['radar'], '50%')
        archive = Path(self.tmp.name) / 'backup.zip'
        portability.create_backup(self.service, archive)
        restored, _ = portability.restore_backup(self.service, archive)
        self.assertEqual(restored.forest.report(restored.config['categorias'])['rows'][0]['matched'], 1)
