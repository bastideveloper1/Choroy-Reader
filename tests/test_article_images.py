import io
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image
from choroy_reader import core
from choroy_reader.service import Service


class ArticleImageTests(unittest.TestCase):
    def test_images_follow_paragraphs_and_exclude_navigation(self):
        html = '<nav><img src="nav.jpg"></nav><article><p>Uno.</p><img data-src="/a.jpg"><p>Dos.</p><img srcset="b.jpg 400w, c.jpg 800w"><img src="javascript:bad"><img src="/a.jpg"></article>'
        images = core.article_images(html, 'https://example.com/post', core.article_text(html))
        self.assertEqual([(x['url'], x['paragraph']) for x in images], [('https://example.com/a.jpg', 0), ('https://example.com/c.jpg', 1)])

    def test_images_survive_restart_and_offline_download(self):
        html = b'<article><p>First.</p><img src="/picture.png"><p>Last.</p></article>'
        data = io.BytesIO()
        Image.new('RGB', (10, 10)).save(data, 'PNG')
        with tempfile.TemporaryDirectory() as tmp:
            service = Service(tmp)
            article = dict(link='https://example.com/post', titulo='Test', imagen=b'cover')
            with patch.object(core, 'download', side_effect=lambda url, **kw: html if url == article['link'] else data.getvalue()):
                result = service.read(article)
            self.assertTrue(result['imagenes_cuerpo'][0]['source'].startswith('data:image/jpeg;base64,'))
            service.library.save('descargas', result)
            with patch.object(core, 'download', side_effect=AssertionError('Unexpected network')):
                restored = Service(tmp)
                self.assertEqual(restored.read(article)['imagenes_cuerpo'], result['imagenes_cuerpo'])
                self.assertEqual(restored.read(article, offline=True)['imagenes_cuerpo'], result['imagenes_cuerpo'])
