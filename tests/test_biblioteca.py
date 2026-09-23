import ast
import io
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

from biblioteca import Biblioteca, coincidencias, puntuar_radar


class BibliotecaTests(unittest.TestCase):
    def test_guardar_descargar_reabrir_y_borrar_independientes(self):
        with tempfile.TemporaryDirectory() as tmp:
            biblioteca = Biblioteca(tmp)
            articulo = dict(link='https://example.com/a?x=../../z', titulo='Título',
                            cuerpo='Texto sin conexión', imagen=b'imagen',
                            fecha=datetime.now(timezone.utc), fuente='Fuente')
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
            biblioteca = Biblioteca(tmp)
            with self.assertRaises(ValueError):
                biblioteca.guardar('descargas', {'link': 'https://example.com'})
            self.assertEqual(biblioteca.listar('descargas'), [])

    def test_archivo_danado_no_rompe_listado(self):
        with tempfile.TemporaryDirectory() as tmp:
            biblioteca = Biblioteca(tmp)
            biblioteca.guardar('guardados', {'link': 'https://example.com', 'titulo': 'A'})
            (Path(tmp) / 'guardados' / 'danado.json').write_text('no json')
            self.assertEqual(len(biblioteca.listar('guardados')), 1)

    def test_busqueda_ignora_mayusculas_y_acentos_con_indices_correctos(self):
        texto = 'La ciberseguridad y la INFORMACIÓN. Información útil.'
        rangos = coincidencias(texto, 'informacion')
        self.assertEqual([texto[a:b] for a, b in rangos], ['INFORMACIÓN', 'Información'])
        self.assertEqual(coincidencias(texto, ''), [])

    def test_radar_prioriza_variedad_y_luego_frecuencia(self):
        palabras = ['seguridad', 'IA', 'privacidad', 'IA', '']
        self.assertEqual(puntuar_radar('Seguridad e IA', 'Privacidad, privacidad.', palabras), (3, 4))
        self.assertEqual(puntuar_radar('Social', 'viaje', ['IA']), (0, 0))
        self.assertGreater(puntuar_radar('Seguridad e IA', '', palabras),
                           puntuar_radar('Seguridad', 'seguridad seguridad', palabras))


def extraer_funcion(nombre, interior=None):
    arbol = ast.parse(Path('noticias.py').read_text())
    nodo = next(n for n in arbol.body if isinstance(n, ast.FunctionDef) and n.name == nombre)
    if interior:
        nodo = next(n for n in nodo.body if isinstance(n, ast.FunctionDef) and n.name == interior)
    return compile(ast.Module(body=[nodo], type_ignores=[]), '<funcion>', 'exec')


class IntegracionTests(unittest.TestCase):
    def test_lectura_descargada_no_accede_a_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            biblioteca = Biblioteca(tmp)
            biblioteca.guardar('descargas', {'link': 'https://example.com', 'cuerpo': 'Texto local'})
            red = Mock(side_effect=AssertionError('No debe usar red'))
            contexto = dict(biblioteca=biblioteca, textos_articulos={}, descargar=red)
            exec(extraer_funcion('contenido_para_articulo'), contexto)
            cuerpo, _ = contexto['contenido_para_articulo']({'link': 'https://example.com'})
            self.assertEqual(cuerpo, 'Texto local')
            red.assert_not_called()

    def test_colores_no_borran_otros_fragmentos(self):
        class Texto:
            tags = {'destacado_lila': set(), 'destacado_azul': set(), 'destacado_amarillo': set()}
            def tag_remove(self, tag, inicio, fin):
                self.tags[tag].difference_update(range(inicio, fin))
            def tag_add(self, tag, inicio, fin):
                self.tags[tag].update(range(inicio, fin))
            def tag_raise(self, tag):
                pass
        texto = Texto()
        contexto = dict(texto=texto, nombres_marcador=['lila', 'azul', 'amarillo'], marcador={'color': 'lila'})
        exec(extraer_funcion('_abrir_articulo', 'marcar_rango'), contexto)
        marcar = contexto['marcar_rango']
        marcar(0, 8)
        contexto['marcador']['color'] = 'azul'
        marcar(10, 20)
        contexto['marcador']['color'] = 'amarillo'
        marcar(15, 25)
        self.assertEqual(texto.tags['destacado_lila'], set(range(8)))
        self.assertEqual(texto.tags['destacado_azul'], set(range(10, 15)))
        self.assertEqual(texto.tags['destacado_amarillo'], set(range(15, 25)))


if __name__ == '__main__':
    unittest.main()

class CitaTests(unittest.TestCase):
    def test_envolver_no_corta_palabras(self):
        dibujo = Mock()
        dibujo.textlength.side_effect = lambda texto, font: len(texto)
        contexto = dict(dibujo=dibujo)
        exec(extraer_funcion('crear_imagen_cita', 'envolver'), contexto)
        lineas = contexto['envolver']('La información necesita contexto y claridad', None, 15)
        self.assertEqual(' '.join(lineas), 'La información necesita contexto y claridad')
        self.assertIn('información', lineas[0])
        self.assertTrue(all(len(linea) <= 15 for linea in lineas))

class ArrastreTests(unittest.TestCase):
    def test_destaca_intervalo_al_cruzar_lineas_en_ambos_sentidos(self):
        from types import SimpleNamespace
        for anterior, actual, esperado in [
            (('1.3', '1.7', 10, 15), ('2.5', '2.9'), ('1.3', '2.9')),
            (('3.5', '3.9', 50, 15), ('1.2', '1.6'), ('1.2', '3.9')),
            (('1.3', '1.7', 10, 15), ('1.80', '1.87'), ('1.3', '1.87')),
        ]:
            texto = Mock()
            texto.index.side_effect = lambda i: actual[0] if i.endswith('wordstart') else actual[1] if i.endswith('wordend') else actual[0]
            texto.bbox.return_value = (10, 30, 20, 20)
            texto.get.return_value = 'palabra'
            texto.tag_names.return_value = []
            marcar = Mock()
            contexto = dict(texto=texto, marcador={'activo': True, 'ultimo': anterior}, marcar_rango=marcar)
            exec(extraer_funcion('_abrir_articulo', 'sobre_destacado'), contexto)
            contexto['sobre_destacado'](SimpleNamespace(x=15, y=35, state=0x100))
            marcar.assert_called_once_with(*esperado)

    def test_huecos_no_interrumpen_arrastre_y_hover_no_pinta(self):
        from types import SimpleNamespace
        texto = Mock()
        texto.index.return_value = '2.0'
        texto.bbox.return_value = None
        anterior = ('1.2', '1.8', 10, 15)
        contexto = dict(texto=texto, marcador={'activo': True, 'ultimo': anterior}, marcar_rango=Mock())
        exec(extraer_funcion('_abrir_articulo', 'sobre_destacado'), contexto)
        contexto['sobre_destacado'](SimpleNamespace(x=15, y=30, state=0x100))
        self.assertEqual(contexto['marcador']['ultimo'], anterior)
        contexto['marcar_rango'].assert_not_called()
        contexto['sobre_destacado'](SimpleNamespace(x=15, y=30, state=0))
        self.assertIsNone(contexto['marcador']['ultimo'])
