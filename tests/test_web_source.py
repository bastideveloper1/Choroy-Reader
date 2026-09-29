import tempfile
import unittest
from unittest.mock import patch
from choroy_reader import core
from choroy_reader.service import Service
from choroy_reader.web_source import extract_publications


class WebSourceTests(unittest.TestCase):
    def test_html_extracts_editorial_links_and_metadata(self):
        html = '''<nav><h2><a href="/menu">Menú de navegación</a></h2></nav>
        <article><header><h2><a href="/news/first?utm_source=home#top">Primera publicación</a></h2></header>
        <time datetime="2026-09-28T10:00:00Z"></time><img data-src="/photo.jpg">
        <a href="/author/editor">Nombre del autor</a><a href="/news/first">Leer más</a></article>
        <h3><a href="/news/second">Segunda publicación</a></h3>
        <h2><a href="https://elsewhere.example/ad">Un anuncio externo</a></h2>
        <h2><a href="/blog">Volver al blog</a></h2>
        <footer><h2><a href="/terms">Términos del servicio</a></h2></footer>'''
        entries = extract_publications(html, 'https://example.com/blog')
        self.assertEqual([x[1] for x in entries], ['https://example.com/news/first', 'https://example.com/news/second'])
        self.assertEqual(entries[0][2:], ('https://example.com/photo.jpg', '2026-09-28T10:00:00Z'))
        self.assertEqual(len(extract_publications(html, 'https://example.com/blog', maximum=1)), 1)

    def test_structured_publications_deduplicate_html(self):
        html = '''<script type="application/ld+json">{"@graph":[{"@type":"NewsArticle","headline":"Noticia estructurada","url":"/story","datePublished":"2026-09-28","image":{"url":"/image.jpg"}},
        {"@type":"ItemList","itemListElement":[{"@type":"ListItem","item":{"name":"Otra publicación","url":"/second"}}]}]}</script>
        <script type="application/ld+json">invalid</script>
        <h2><a href="/story">Noticia estructurada</a></h2>'''
        entries = extract_publications(html, 'https://example.com/')
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0][3], '2026-09-28')

    def test_web_source_persists_provenance_dates_and_reuses_detection(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = Service(tmp)
            source = dict(nombre='Sitio', url='https://example.com/blog', traduccion_es=False)
            service.config['categorias'] = [dict(nombre='Noticias', sitios=[source])]
            html = b'<article><h2><a href="/first">Primera noticia</a></h2></article><h2><a href="/second">Segunda noticia</a></h2>'
            with patch.object(service, 'fetch_favicon'), patch.object(core, 'discover_feed', return_value=None) as discover, patch.object(core, 'download', return_value=html):
                result = service.refresh()
                service.apply_refresh(result)
                first = service.all_articles()[0]
                self.assertEqual(first['link'], 'https://example.com/first')
                self.assertEqual(first['origen'], 'web')
                self.assertTrue(first['fecha_detectada'])
                self.assertTrue(source['extraccion_web'])
                self.assertFalse(source['sin_feed'])
                service.apply_refresh(service.refresh())
                self.assertEqual(discover.call_count, 1)
                self.assertEqual(service.all_articles()[0]['fecha'], first['fecha'])
            reopened = Service(tmp)
            self.assertEqual(reopened.all_articles()[0]['origen'], 'web')
            with patch.object(reopened, 'fetch_favicon'), patch.object(core, 'download', return_value=b'<p>Layout changed</p>'):
                reopened.apply_refresh(reopened.refresh())
            self.assertEqual(len(reopened.all_articles()), 2)
            reopened.library.save('guardados', first)
            self.assertTrue(reopened.library.read('guardados', first['link'])['fecha_detectada'])
