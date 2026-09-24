import io
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from choroy_reader.library import Library, find_matches, score_radar
from choroy_reader import core
from choroy_reader.service import Service


class LibraryTests(unittest.TestCase):
    def test_missing_feed_is_distinct_from_network_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = Service(tmp)
            source = {'nombre': 'Sitio', 'url': 'https://example.com'}
            service.config['categorias'] = [{'nombre': 'Interés', 'sitios': [source]}]
            with patch.object(core, 'discover_feed', return_value=None), patch.object(core, 'download', return_value=b'<html></html>'):
                result = service.refresh()
                service.apply_refresh(result)
            self.assertTrue(source['sin_feed'])
            self.assertEqual(result[2], [])
            source.pop('sin_feed')
            with patch.object(core, 'discover_feed', return_value=None), patch.object(core, 'download', side_effect=OSError('Sin conexión')):
                result = service.refresh()
                service.apply_refresh(result)
            self.assertNotIn('sin_feed', source)
            self.assertEqual(len(result[2]), 1)

    def test_bookmarks_and_downloads_persist_independently(self):
        with tempfile.TemporaryDirectory() as tmp:
            library = Library(tmp)
            article = dict(link='https://example.com/a?x=../../z', titulo='Título', cuerpo='Texto sin conexión', imagen=b'imagen', fecha=datetime.now(timezone.utc), fuente='Fuente')
            library.save('guardados', article)
            library.save('descargas', article)
            reopened = Library(tmp)
            loaded = reopened.list_items('descargas')[0]
            self.assertEqual(loaded['cuerpo'], article['cuerpo'])
            self.assertEqual(loaded['imagen'], article['imagen'])
            self.assertEqual(loaded['fecha'], article['fecha'])
            reopened.delete('descargas', article['link'])
            self.assertFalse(reopened.contains('descargas', article['link']))
            self.assertTrue(reopened.contains('guardados', article['link']))
            reopened.delete('guardados', article['link'])
            self.assertEqual(reopened.list_items('guardados'), [])

    def test_empty_body_cannot_be_downloaded(self):
        with tempfile.TemporaryDirectory() as tmp:
            b = Library(tmp)
            with self.assertRaises(ValueError): b.save('descargas', {'link': 'https://example.com'})
            self.assertEqual(b.list_items('descargas'), [])

    def test_invalid_file_does_not_break_listing(self):
        with tempfile.TemporaryDirectory() as tmp:
            b = Library(tmp)
            b.save('guardados', {'link': 'https://example.com', 'titulo': 'A'})
            (Path(tmp)/'guardados'/'danado.json').write_text('no json')
            self.assertEqual(len(b.list_items('guardados')), 1)

    def test_search_ignores_case_and_accents(self):
        text='La INFORMACIÓN. Información útil.'
        self.assertEqual([text[a:b] for a,b in find_matches(text,'informacion')],['INFORMACIÓN','Información'])
        self.assertEqual(find_matches(text,''),[])

    def test_radar_ranks_variety_before_frequency(self):
        words=['seguridad','IA','privacidad','IA','']
        self.assertEqual(score_radar('Seguridad e IA','Privacidad, privacidad.',words),(3,4))
        self.assertEqual(score_radar('Social','viaje',['IA']),(0,0))
        self.assertGreater(score_radar('Seguridad e IA','',words),score_radar('Seguridad','seguridad seguridad',words))


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.service=Service(self.tmp.name)

    def test_downloaded_article_needs_no_network(self):
        article={'link':'https://example.com','cuerpo':'Texto local'}
        self.service.library.save('descargas',article)
        with patch.object(core,'download',side_effect=AssertionError('No debe usar red')):
            self.assertEqual(self.service.read({'link':article['link']},offline=True)['cuerpo'],'Texto local')

    def test_config_preserves_removed_categories(self):
        self.service.config['categorias']=[]
        self.service.save_config()
        self.assertEqual(Service(self.tmp.name).config['categorias'],[])

    def test_search_category_and_radar_filters(self):
        s=self.service
        s.config.update(categorias=[{'nombre':'Tech','sitios':[{'nombre':'A','url':'a'}]}],radar_activo=True,radar_palabras=['seguridad','privacidad'])
        s.articles={'a':[dict(link='1',titulo='Seguridad',fecha=None,source_url='a'),dict(link='2',titulo='SEGURIDAD y privacidad',fecha=None,source_url='a')]}
        self.assertEqual([a['link'] for a in s.filtered(category='Tech',query='seguridad')],['2','1'])
        self.assertEqual(s.filtered(query='imposible'),[])

    def test_feed_and_content_parsing(self):
        rss=b'<rss><channel><item><title>Titulo</title><link>https://example.com/a</link><description>&lt;p&gt;Contenido&lt;/p&gt;&lt;img src="/cover.jpg"&gt;</description></item></channel></rss>'
        articles=core.parse_feed(rss)
        self.assertEqual(articles[0][2],'/cover.jpg')
        self.assertIn('Contenido',core.feed_content['https://example.com/a'])

    def test_quote_export_and_word_wrapping(self):
        from PIL import Image, ImageDraw
        draw_original=ImageDraw.ImageDraw.multiline_text
        drawn=[]
        def record(draw,xy,text,*args,**kwargs):
            drawn.append(text)
            return draw_original(draw,xy,text,*args,**kwargs)
        quote='La información necesita contexto y claridad para compartir ideas con otras personas.'
        with patch.object(ImageDraw.ImageDraw,'multiline_text',record):
            image=core.create_quote_image(quote,'Fuente','https://example.com',title='Original title',theme='periodico',color='#202020')
        self.assertIn(quote,[' '.join(text.split()) for text in drawn])
        self.assertEqual(image.getpixel((0,0)),(230,230,230))
        for fmt in ('PNG','JPEG'):
            out=io.BytesIO();image.save(out,fmt);out.seek(0)
            self.assertEqual(Image.open(out).format,fmt)


if __name__=='__main__': unittest.main()
