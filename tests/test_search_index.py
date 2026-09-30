import sqlite3
import unittest
from unittest.mock import patch

from choroy_reader.search_index import SearchIndex


class SearchIndexTests(unittest.TestCase):
    def test_fts_and_fallback_return_identical_literal_matches(self):
        documents = [
            ('a', 'INFORMACIÓN chilena', 'Astronomía y traducción guardada'),
            ('b', 'Otro título: "hola" OR mundo', 'Información adicional'),
            ('c', '日本語の記事 y pingüino', 'Texto\ncon salto'),
        ]
        for use_fts in (True, False):
            index = SearchIndex(use_fts=use_fts)
            self.addCleanup(index.close)
            for query in ('informacion', 'astronomia', 'in', 'ñ', '日本語',
                          '"hola"', 'OR', 'titulo:', '*', 'pingüino',
                          'con salto', 'no existe', ''):
                for include_body in (True, False):
                    with self.subTest(fts=use_fts, query=query, body=include_body):
                        fallback = SearchIndex(use_fts=False)
                        try:
                            expected = fallback.match(documents, query, include_body)
                        finally:
                            fallback.close()
                        self.assertEqual(index.match(documents, query, include_body), expected)

    def test_updates_deletions_and_collection_switches(self):
        for use_fts in (True, False):
            index = SearchIndex(use_fts=use_fts)
            self.addCleanup(index.close)
            self.assertEqual(index.match([('a', 'Anterior', '')], 'anterior'), {'a'})
            self.assertEqual(index.match([('a', 'Nuevo', '')], 'anterior'), set())
            self.assertEqual(index.match([('a', 'Nuevo', '')], 'nuevo'), {'a'})
            self.assertEqual(index.match([('b', 'Nuevo', '')], 'nuevo'), {'b'})
            self.assertEqual(index.match([], 'nuevo'), set())

    def test_missing_fts_extension_falls_back(self):
        with patch('choroy_reader.search_index.sqlite3.connect') as connect:
            connect.return_value.execute.side_effect = sqlite3.OperationalError('no such module: fts5')
            index = SearchIndex()
            self.addCleanup(index.close)
            self.assertFalse(index.available)
            self.assertEqual(index.match([('a', 'Información', '')], 'informacion'), {'a'})


if __name__ == '__main__':
    unittest.main()
