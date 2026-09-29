import io
import json
import unittest
from unittest.mock import patch
from urllib.error import URLError
from choroy_reader.updates import check_updates


class UpdateTests(unittest.TestCase):
    def check(self, releases, installed='0.1.1'):
        with patch('choroy_reader.updates.urlopen', return_value=io.StringIO(json.dumps(releases))):
            return check_updates('https://github.com/owner/repo', installed)

    def test_numeric_order_beta_drafts_and_invalid_tags(self):
        result = self.check([
            dict(tag_name='v0.1.9'),
            dict(tag_name='v0.1.10', prerelease=True, body='Novedades'),
            dict(tag_name='v99.0.0', draft=True),
            dict(tag_name='nightly'),
        ])
        self.assertTrue(result['available'])
        self.assertEqual(result['version'], 'v0.1.10')
        self.assertEqual(result['notes'], 'Novedades')
        self.assertIn('Beta', result['message'])
        self.assertEqual(result['url'], 'https://github.com/owner/repo/releases/tag/v0.1.10')

    def test_equal_older_and_empty(self):
        for tag in ('v0.1.1', 'v0.1.0'):
            self.assertFalse(self.check([dict(tag_name=tag)])['available'])
        self.assertFalse(self.check([])['available'])

    def test_pagination(self):
        batches = [io.StringIO(json.dumps([dict(tag_name='v0.1.0')] * 100)),
                   io.StringIO(json.dumps([dict(tag_name='v0.2.0')]))]
        with patch('choroy_reader.updates.urlopen', side_effect=batches) as request:
            result = check_updates('https://github.com/owner/repo', '0.1.1')
        self.assertTrue(result['available'])
        self.assertIn('page=2', request.call_args.args[0].full_url)

    def test_network_failure(self):
        with patch('choroy_reader.updates.urlopen', side_effect=URLError('offline')):
            with self.assertRaises(URLError):
                check_updates('https://github.com/owner/repo', '0.1.1')
