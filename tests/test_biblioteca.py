import io
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from biblioteca import Biblioteca, coincidencias, puntuar_radar
from minimalfeed import core
from minimalfeed.service import Service


class BibliotecaTests(unittest.TestCase):
    def test_guardar_descargar_reabrir_y_borrar_independientes(self):
        with tempfile.TemporaryDirectory() as tmp:
            biblioteca = Biblioteca(tmp)
            articulo = dict(link='https://example.com/a?x=../../z', titulo='Título', cuerpo='Texto sin conexión', imagen=b'imagen', fecha=datetime.now(timezone.utc), fuente='Fuente')
            biblioteca.guardar('guardados', articulo)
            biblioteca.guardar('descargas', articulo)
            otra = Biblioteca(tmp)
            copia = otra.listar('descargas')[0]
            self.assertEqual(copia['cuerpo'], articulo['cuerpo'])
            self.assertEqual(copia['imagen'], articulo['imagen'])
            self.assertEqual(copia['fecha'], articulo['fecha'])
            otra.borrar('descargas', articulo['link'])
            self.assertFalse(otra.contiene('descargas', articulo['link']))
            self.assertTrue(otra.contiene('guardados', articulo['link']))
            otra.borrar('guardados', articulo['link'])
            self.assertEqual(otra.listar('guardados'), [])

    def test_descarga_sin_texto_no_se_guarda(self):
        with tempfile.TemporaryDirectory() as tmp:
            b = Biblioteca(tmp)
            with self.assertRaises(ValueError): b.guardar('descargas', {'link': 'https://example.com'})
            self.assertEqual(b.listar('descargas'), [])

    def test_archivo_danado_no_rompe_listado(self):
        with tempfile.TemporaryDirectory() as tmp:
            b = Biblioteca(tmp)
            b.guardar('guardados', {'link': 'https://example.com', 'titulo': 'A'})
            (Path(tmp)/'guardados'/'danado.json').write_text('no json')
            self.assertEqual(len(b.listar('guardados')), 1)

    def test_busqueda_ignora_mayusculas_y_acentos(self):
        text='La INFORMACIÓN. Información útil.'
        self.assertEqual([text[a:b] for a,b in coincidencias(text,'informacion')],['INFORMACIÓN','Información'])
        self.assertEqual(coincidencias(text,''),[])

    def test_radar_prioriza_variedad_y_luego_frecuencia(self):
        words=['seguridad','IA','privacidad','IA','']
        self.assertEqual(puntuar_radar('Seguridad e IA','Privacidad, privacidad.',words),(3,4))
        self.assertEqual(puntuar_radar('Social','viaje',['IA']),(0,0))
        self.assertGreater(puntuar_radar('Seguridad e IA','',words),puntuar_radar('Seguridad','seguridad seguridad',words))


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.service=Service(self.tmp.name)

    def test_lectura_descargada_no_accede_a_red(self):
        article={'link':'https://example.com','cuerpo':'Texto local'}
        self.service.library.guardar('descargas',article)
        with patch.object(core,'descargar',side_effect=AssertionError('No debe usar red')):
            self.assertEqual(self.service.read({'link':article['link']},offline=True)['cuerpo'],'Texto local')

    def test_config_existente_no_reintroduce_categorias_eliminadas(self):
        self.service.config['categorias']=[]
        self.service.save_config()
        self.assertEqual(Service(self.tmp.name).config['categorias'],[])

    def test_busqueda_categoria_y_radar(self):
        s=self.service
        s.config.update(categorias=[{'nombre':'Tech','sitios':[{'nombre':'A','url':'a'}]}],radar_activo=True,radar_palabras=['seguridad','privacidad'])
        s.articles={'a':[dict(link='1',titulo='Seguridad',fecha=None,source_url='a'),dict(link='2',titulo='SEGURIDAD y privacidad',fecha=None,source_url='a')]}
        self.assertEqual([a['link'] for a in s.filtered(category='Tech',query='seguridad')],['2','1'])
        self.assertEqual(s.filtered(query='imposible'),[])

    def test_feed_y_contenido(self):
        rss=b'<rss><channel><item><title>Titulo</title><link>https://example.com/a</link><description>&lt;p&gt;Contenido&lt;/p&gt;&lt;img src="/cover.jpg"&gt;</description></item></channel></rss>'
        articles=core.parsear_feed(rss)
        self.assertEqual(articles[0][2],'/cover.jpg')
        self.assertIn('Contenido',core.contenido_feed['https://example.com/a'])

    def test_cita_png_jpg_y_palabras_completas(self):
        from PIL import Image, ImageDraw
        draw_original=ImageDraw.ImageDraw.multiline_text
        drawn=[]
        def record(draw,xy,text,*args,**kwargs):
            drawn.append(text)
            return draw_original(draw,xy,text,*args,**kwargs)
        quote='La información necesita contexto y claridad para compartir ideas con otras personas.'
        with patch.object(ImageDraw.ImageDraw,'multiline_text',record):
            image=core.crear_imagen_cita(quote,'Fuente','https://example.com',titulo='Original title',tema='periodico',color='#202020')
        self.assertIn(quote,[' '.join(text.split()) for text in drawn])
        self.assertEqual(image.getpixel((0,0)),(230,230,230))
        for fmt in ('PNG','JPEG'):
            out=io.BytesIO();image.save(out,fmt);out.seek(0)
            self.assertEqual(Image.open(out).format,fmt)


if __name__=='__main__': unittest.main()
