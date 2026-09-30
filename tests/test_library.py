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
    def test_saved_order_uses_addition_time_even_with_radar_and_updates(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = Service(tmp)
            service.config.update(radar_activo=True, radar_palabras=['seguridad'])
            older_save = dict(link='https://example.com/first', titulo='Seguridad', fecha=datetime.now(timezone.utc))
            newer_save = dict(link='https://example.com/second', titulo='Otra noticia', fecha=datetime(2000, 1, 1, tzinfo=timezone.utc))
            with patch('choroy_reader.library.time.time_ns', return_value=100):
                service.library.save('guardados', older_save)
            with patch('choroy_reader.library.time.time_ns', return_value=200):
                service.library.save('guardados', newer_save)
            with patch('choroy_reader.library.time.time_ns', return_value=300):
                service.library.save('guardados', dict(older_save, cuerpo='Contenido actualizado'))
            self.assertEqual([a['link'] for a in service.filtered('guardados')], [newer_save['link'], older_save['link']])
            service.save_config()
            restored = Service(tmp)
            self.assertEqual([a['link'] for a in restored.filtered('guardados')], [newer_save['link'], older_save['link']])
            self.assertEqual(restored.filtered('guardados', query='Seguridad')[0]['guardado_en'], 100)
            restored.library.delete('guardados', older_save['link'])
            with patch('choroy_reader.library.time.time_ns', return_value=400):
                restored.library.save('guardados', older_save)
            self.assertEqual(restored.filtered('guardados')[0]['link'], older_save['link'])

    def test_legacy_saved_date_survives_content_update(self):
        import json
        import os
        with tempfile.TemporaryDirectory() as tmp:
            library = Library(tmp)
            article = dict(link='https://example.com/legacy', titulo='Anterior')
            path = library.path('guardados', article['link'])
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(article))
            os.utime(path, ns=(123456789, 123456789))
            # Windows file times use 100 ns ticks; preserve what the filesystem stores.
            saved_at = path.stat().st_mtime_ns
            library.save('guardados', dict(article, titulo='Actualizado'))
            self.assertEqual(library.read('guardados', article['link'])['guardado_en'], saved_at)

    def test_refresh_reuses_cover_and_translated_title(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = Service(tmp)
            source = dict(nombre='Fuente', url='https://example.com', url_feed='https://example.com/rss')
            article = dict(link='https://example.com/a', titulo='A title', titulo_es='Un título', traducir_es=True, imagen=b'cached', fecha=datetime.now(timezone.utc))
            service.articles[source['url']] = [article]
            with patch.object(service, 'fetch_favicon'), patch.object(core, 'get_articles', return_value=[(article['titulo'], article['link'], None, article['fecha'].isoformat())]), patch.object(core, 'translate_text') as translate, patch.object(service, 'fetch_image') as image:
                _, articles = service.fetch_source(source, service.config)
                self.assertEqual(articles[0]['imagen'], b'cached')
                self.assertEqual(articles[0]['titulo_es'], 'Un título')
                translate.assert_not_called()
                image.assert_not_called()

    def test_cover_cache_validates_headers_without_decoding_pixels(self):
        import io
        from PIL import Image
        output = io.BytesIO()
        Image.new('RGB', (20, 20)).save(output, 'PNG')
        data = output.getvalue()
        with tempfile.TemporaryDirectory() as tmp:
            service = Service(tmp)
            with patch('PIL.PngImagePlugin.PngImageFile.load', side_effect=AssertionError('Synchronous decode')):
                first = service.image_url(data)
                self.assertTrue(first.startswith('file:'))
                self.assertEqual(service.image_url(data), first)
                self.assertEqual(service.image_url(b'<svg></svg>'), '')
            self.assertEqual(len(list((Path(tmp) / 'cache' / 'images').iterdir())), 1)

    def test_history_retention_protection_recovery_and_identity(self):
        import time
        with tempfile.TemporaryDirectory() as tmp:
            service = Service(tmp)
            service.config['historial_dias'] = 30
            articles = {name: dict(link='https://example.com/' + name, titulo=name, fecha=datetime.now(), cuerpo='Texto', source_url='https://example.com')
                        for name in ('old', 'pending', 'saved', 'downloaded', 'archived')}
            for name, article in articles.items():
                service.remember_article(article)
                if name != 'pending':
                    service.seen.add(article['link'])
            for name, kind in [('saved', 'guardados'), ('downloaded', 'descargas'), ('archived', 'archivados')]:
                service.library.save(kind, articles[name])
            old = articles['old']
            service.dismissed.add(old['link'])
            service.reader_store.save_original(old['link'], 'Texto conservado')
            service.save_config()
            later = time.time() + 31 * 86400
            self.assertEqual(service.cleanup_history(later), 1)
            self.assertFalse(service.library.contains('historial', old['link']))
            self.assertTrue(service.library.contains('retirados', old['link']))
            self.assertEqual(len(service.library.list_items('historial')), 4)
            # Repeated RSS entries must not recreate a retired history entry.
            service.remember_article(old)
            self.assertFalse(service.library.contains('historial', old['link']))
            service.restore_history(old['link'], later)
            self.assertTrue(service.library.contains('historial', old['link']))
            self.assertEqual(service.cleanup_history(later), 0)
            service.cleanup_history(later + 31 * 86400)
            service.cleanup_history(later + 62 * 86400)
            self.assertFalse(service.library.contains('retirados', old['link']))
            reopened = Service(tmp)
            reopened.remember_article(old)
            self.assertFalse(reopened.library.contains('historial', old['link']))
            self.assertIn(old['link'], reopened.seen)
            self.assertIn(old['link'], reopened.dismissed)
            self.assertEqual(reopened.reader_store.read(old['link'])['original'], 'Texto conservado')

    def test_article_period_boundaries_and_persistence(self):
        from datetime import timedelta
        with tempfile.TemporaryDirectory() as tmp:
            service = Service(tmp)
            now = datetime(2026, 9, 24, 12).astimezone()
            today = now.replace(hour=0)
            self.assertTrue(service.in_period(today, now=now))
            self.assertFalse(service.in_period(today - timedelta(seconds=1), now=now))
            self.assertFalse(service.in_period(None, now=now))
            self.assertFalse(service.in_period(now + timedelta(days=1), now=now))
            for period, days in [('semana', 6), ('mes', 29)]:
                config = {'periodo_articulos': period}
                self.assertTrue(service.in_period(today - timedelta(days=days), config, now))
                self.assertFalse(service.in_period(today - timedelta(days=days, seconds=1), config, now))
            service.config['periodo_articulos'] = 'ano'
            service.save_config()
            self.assertTrue(Service(tmp).in_period(now.replace(month=1, day=1), now=now))

    def test_fetch_filters_dates_before_limit_and_deduplicates(self):
        from datetime import timedelta
        with tempfile.TemporaryDirectory() as tmp:
            service = Service(tmp)
            now = datetime.now().astimezone()
            source = {'nombre': 'Fuente', 'url': 'https://example.com', 'url_feed': 'https://example.com/rss', 'limite_articulos': 2}
            raw = [('Viejo', 'https://example.com/old', None, (now - timedelta(days=3)).isoformat())]
            raw += [('Actual', f'https://example.com/{n}', None, now.isoformat()) for n in [1, 1, 2, 3]]
            with patch.object(service, 'fetch_favicon'), patch.object(service, 'fetch_image', return_value=None), patch.object(core, 'get_articles', return_value=raw):
                _, articles = service.fetch_source(source, {'mostrar_titulo_es': False})
            self.assertEqual(len(articles), 2)
            self.assertEqual(len({a['link'] for a in articles}), 2)
            self.assertNotIn('https://example.com/old', [a['link'] for a in articles])

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
        s.articles={'a':[dict(link='1',titulo='Seguridad',fecha=datetime.now(),source_url='a'),dict(link='2',titulo='SEGURIDAD y privacidad',fecha=datetime.now(),source_url='a')]}
        self.assertEqual([a['link'] for a in s.filtered(category='Tech',query='seguridad')],['2','1'])
        self.assertEqual(s.filtered(query='imposible'),[])

    def test_saved_search_includes_original_and_translation_only_when_requested(self):
        s = self.service
        article = dict(link='https://example.com/saved', titulo='Título visible', titulo_es='Translated heading')
        s.library.save('guardados', article)
        s.reader_store.save_translation(article['link'], 'Astronomy snapshot', 'Traducción sobre astronomía')
        self.assertEqual(len(s.filtered(page='guardados', query='heading')), 1)
        self.assertEqual(s.filtered(page='guardados', query='astronomia'), [])
        for query in ('astronomy', 'astronomia'):
            self.assertEqual(len(s.filtered(page='guardados', query=query, include_body=True)), 1)
        s.library.delete('guardados', article['link'])
        self.assertEqual(s.filtered(page='guardados', query='astronomia', include_body=True), [])

    def test_feed_and_content_parsing(self):
        rss=b'<rss><channel><item><title>Titulo</title><link>https://example.com/a</link><description>&lt;p&gt;Contenido&lt;/p&gt;&lt;img src="/cover.jpg"&gt;</description></item></channel></rss>'
        articles=core.parse_feed(rss)
        self.assertEqual(articles[0][2],'/cover.jpg')
        self.assertIn('Contenido',core.feed_content['https://example.com/a'])

    def test_quote_backgrounds_render_solid_and_gradient_colors(self):
        from PIL import ImageColor
        for key in ('marfil', 'grad_aurora', 'grad_amanecer'):
            preset = next(item for item in core.QUOTE_BACKGROUNDS if item['key'] == key)
            image = core.create_quote_image('Una cita de prueba.', 'Fuente', 'https://example.com/article', title='Título', background=key)
            self.assertEqual(image.size, (2160, 2160))
            self.assertEqual(image.getpixel((0, 0)), ImageColor.getrgb(preset['start']))
            self.assertEqual(image.getpixel((0, 2159)), ImageColor.getrgb(preset['end']))
            if preset['start'] != preset['end']:
                self.assertNotEqual(image.getpixel((0, 1080)), image.getpixel((0, 0)))
            output = io.BytesIO()
            image.save(output, 'PNG')
            from PIL import Image
            output.seek(0)
            with Image.open(output) as reopened:
                self.assertEqual(reopened.getpixel((0, 2159)), ImageColor.getrgb(preset['end']))

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
