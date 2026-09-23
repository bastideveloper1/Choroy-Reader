"""Persistencia local y búsqueda de artículos, sin dependencias de interfaz."""
import base64
import hashlib
import json
import os
import re
import tempfile
import unicodedata
from pathlib import Path
from datetime import datetime


def normalizar(texto):
    return ''.join(c for c in unicodedata.normalize('NFD', texto.casefold())
                   if unicodedata.category(c) != 'Mn')


def coincidencias(texto, consulta):
    consulta = normalizar(consulta.strip())
    if not consulta:
        return []
    # Conserva posiciones del texto original incluso con acentos compuestos.
    letras, posiciones = [], []
    for i, letra in enumerate(texto):
        for c in normalizar(letra):
            letras.append(c)
            posiciones.append(i)
    return [(posiciones[m.start()], posiciones[m.end() - 1] + 1)
            for m in re.finditer(re.escape(consulta), ''.join(letras))]


def puntuar_radar(titulo, cuerpo, palabras):
    texto = normalizar(titulo + '\n' + cuerpo)
    terminos = set(normalizar(p.strip()) for p in palabras if p.strip())
    encontrados = {p: len(re.findall(r'(?<!\w)' + re.escape(p) + r'(?!\w)', texto)) for p in terminos}
    encontrados = {p: n for p, n in encontrados.items() if n}
    return len(encontrados), sum(encontrados.values())


class Biblioteca:
    def __init__(self, raiz):
        self.raiz = Path(raiz)

    def ruta(self, tipo, link):
        if tipo not in {'guardados', 'descargas'}:
            raise ValueError('Sección no válida')
        return self.raiz / tipo / (hashlib.sha256(link.encode()).hexdigest() + '.json')

    def contiene(self, tipo, link):
        return self.ruta(tipo, link).is_file()

    def guardar(self, tipo, articulo):
        datos = {k: articulo.get(k) for k in ('titulo', 'titulo_es', 'link', 'fuente', 'cuerpo', 'estado_contenido', 'idioma_original', 'traducir_es')}
        if not datos['link']:
            raise ValueError('Artículo sin enlace')
        if tipo == 'descargas' and not datos['cuerpo']:
            raise ValueError('No hay texto disponible para descargar')
        fecha = articulo.get('fecha')
        datos['fecha'] = fecha.isoformat() if isinstance(fecha, datetime) else fecha
        datos['imagen'] = base64.b64encode(articulo.get('imagen') or b'').decode()
        ruta = self.ruta(tipo, datos['link'])
        ruta.parent.mkdir(parents=True, exist_ok=True)
        temporal = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=ruta.parent, delete=False) as f:
                temporal = f.name
                json.dump(datos, f, ensure_ascii=False)
            os.replace(temporal, ruta)
        finally:
            if temporal and os.path.exists(temporal):
                os.unlink(temporal)

    def leer_ruta(self, ruta):
        datos = json.loads(Path(ruta).read_text(encoding='utf-8'))
        datos['imagen'] = base64.b64decode(datos.get('imagen') or '') or None
        try:
            datos['fecha'] = datetime.fromisoformat(datos['fecha']) if datos.get('fecha') else None
        except (ValueError, TypeError):
            datos['fecha'] = None
        return datos

    def leer(self, tipo, link):
        try:
            return self.leer_ruta(self.ruta(tipo, link))
        except (OSError, ValueError, TypeError):
            return None

    def listar(self, tipo):
        self.ruta(tipo, '')  # Valida la sección.
        salida = []
        for ruta in sorted((self.raiz / tipo).glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                salida.append(self.leer_ruta(ruta))
            except (OSError, ValueError, TypeError):
                continue
        return salida

    def borrar(self, tipo, link):
        self.ruta(tipo, link).unlink(missing_ok=True)
