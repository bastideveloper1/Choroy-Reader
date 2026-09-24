"""Motor Python de MinimalFeed. Sin dependencias de Tkinter ni de Qt."""
import io
import os
import re
import json
import gzip
import time
import textwrap
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from html import unescape
from html.parser import HTMLParser
from datetime import datetime
from email.utils import parsedate_to_datetime
from PIL import Image, ImageDraw, ImageFont, ImageOps


class ContenidoHTML(HTMLParser):
    """Extrae texto legible y metadatos sin ejecutar código de la página."""
    def __init__(self):
        super().__init__()
        self.partes = []
        self.imagen = None
        self.omitir = 0

    def handle_starttag(self, tag, attrs):
        atributos = dict(attrs)
        if tag in {"script", "style", "noscript"}:
            self.omitir += 1
        if tag in {"p", "div", "br", "h1", "h2", "h3", "li", "blockquote"}:
            self.partes.append("\n\n")
        if tag == "meta" and (atributos.get("property") or atributos.get("name")) in {"og:image", "twitter:image"}:
            self.imagen = atributos.get("content") or self.imagen
        if tag == "img":
            self.imagen = self.imagen or atributos.get("src") or atributos.get("data-src")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"}:
            self.omitir = max(0, self.omitir - 1)
        if tag in {"p", "div", "h1", "h2", "h3", "li", "blockquote"}:
            self.partes.append("\n\n")

    def handle_data(self, data):
        if not self.omitir:
            self.partes.append(data)

    def texto(self):
        return "\n\n".join(
            re.sub(r"\s+", " ", bloque).strip()
            for bloque in "".join(self.partes).split("\n\n") if bloque.strip()
        )

contenido_feed = {}

def guardar_contenido_feed(link, elemento):
    bloques = []
    for hijo in elemento:
        if hijo.tag.split("}")[-1] in {"encoded", "content", "description", "summary"}:
            bloques.append("".join(hijo.itertext()))
    html = max(bloques, key=len, default="")
    if html:
        contenido_feed[link] = html
    parser = ContenidoHTML()
    parser.feed(html)
    return parser.imagen

def texto_articulo(html):
    # BeautifulSoup permite acotar el texto al cuerpo editorial.
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        for nodo in soup.select("script, style, noscript, nav, header, footer, aside, form"):
            nodo.decompose()
        cuerpo = soup.select_one('[itemprop="articleBody"]') or soup.find("article") or soup.find("main")
        if cuerpo is None:
            return ""
        bloques = [n.get_text(" ", strip=True) for n in cuerpo.select("p, h2, h3, li, blockquote")]
        return "\n\n".join(b for b in bloques if b)
    except ImportError:
        return ""

ARTICULOS_POR_SITIO = 3

MINUTOS_ENTRE_ACTUALIZACIONES = 30

PALETA_TEMAS = {
    "gris": {
        "base": "#8a8f98",
        "base_fuerte": "#b0b7c2",
        "hover": "#dfe7f7",
        "cerrar": "#888888",
        "cerrar_hover": "#dfe7f7",
        "card_bg": "#1d1d1d",
        "card_hover": "#232323",
        "card_borde": "#444444",
        "texto": "#f0f0f0",
        "texto_sec": "#a8a8a8",
        "link": "#4aa3ff",
        "link_hover": "#7ec2ff",
    },
    "morado_neon": {
        "base": "#b86bff",
        "base_fuerte": "#d89cff",
        "hover": "#e7c8ff",
        "cerrar": "#b86bff",
        "cerrar_hover": "#e7c8ff",
        "card_bg": "#1d1d1d",
        "card_hover": "#231b2d",
        "card_borde": "#b86bff",
        "texto": "#f2edff",
        "texto_sec": "#c6b2e5",
        "link": "#b86bff",
        "link_hover": "#d89cff",
    },
    "azul_neon": {
        "base": "#3aa0ff",
        "base_fuerte": "#7bc3ff",
        "hover": "#d8f1ff",
        "cerrar": "#3aa0ff",
        "cerrar_hover": "#d8f1ff",
        "card_bg": "#1d1d1d",
        "card_hover": "#152738",
        "card_borde": "#3aa0ff",
        "texto": "#ebf8ff",
        "texto_sec": "#aed9ff",
        "link": "#3aa0ff",
        "link_hover": "#7bc3ff",
    },
    "amarillo_neon": {
        "base": "#ffd54a",
        "base_fuerte": "#ffe88f",
        "hover": "#fff3bb",
        "cerrar": "#ffd54a",
        "cerrar_hover": "#fff3bb",
        "card_bg": "#1d1d1d",
        "card_hover": "#2a2415",
        "card_borde": "#ffd54a",
        "texto": "#fff8db",
        "texto_sec": "#f0d98c",
        "link": "#ffd54a",
        "link_hover": "#ffe88f",
    },
    "verde_neon": {
        "base": "#48e4a0",
        "base_fuerte": "#8af1c2",
        "hover": "#d8ffe9",
        "cerrar": "#48e4a0",
        "cerrar_hover": "#d8ffe9",
        "card_bg": "#1d1d1d",
        "card_hover": "#122b23",
        "card_borde": "#48e4a0",
        "texto": "#ecfff5",
        "texto_sec": "#bdeed1",
        "link": "#48e4a0",
        "link_hover": "#8af1c2",
    },
    "rosa_neon": {
        "base": "#ff5ecb",
        "base_fuerte": "#ff9ae0",
        "hover": "#ffd3f3",
        "cerrar": "#ff5ecb",
        "cerrar_hover": "#ffd3f3",
        "card_bg": "#1d1d1d",
        "card_hover": "#2d1828",
        "card_borde": "#ff5ecb",
        "texto": "#fff0fb",
        "texto_sec": "#f5c2ea",
        "link": "#ff5ecb",
        "link_hover": "#ff9ae0",
    },
}

NOMBRES_TEMAS = {
    "periodico": "Periódico",
    "gris": "Gris minimalista",
    "morado_neon": "Lila eléctrico",
    "azul_neon": "Azul ártico",
    "amarillo_neon": "Amarillo solar",
    "verde_neon": "Verde menta",
    "rosa_neon": "Rosa cerezo japonés",
}

PALETA_TEMAS["periodico"] = {
    "base": "#454545", "base_fuerte": "#202020", "hover": "#000000",
    "cerrar": "#555555", "cerrar_hover": "#000000",
    "card_bg": "#e6e6e6", "card_hover": "#d8d8d8", "card_borde": "#b5b3ad",
    "texto": "#171717", "texto_sec": "#565656", "link": "#202020", "link_hover": "#000000",
}

def sitio(nombre, url):
    return {
        "nombre": nombre,
        "url": url,
        "url_feed": None,
        "max_articulos": None,      # None = usar ARTICULOS_POR_SITIO
        "intervalo_min": None,      # None = usar MINUTOS_ENTRE_ACTUALIZACIONES
        "mostrar_imagen": False,
        "modo_titulo": "en_es",
        "traduccion_es": True,
        "favicon_personalizado": None,
        "ultima_actualizacion": 0,
    }

CONFIG_INICIAL = {
    "tema": "gris",
    "color": "gris",
    "mostrar_titulo_es": True,
    "articulos_por_fila": 5,
    "categorias": [
        {
            "nombre": "Newspapers: Cybersecurity",
            "sitios": [
                sitio("The Record", "https://therecord.media/"),
                sitio("Cybernews", "https://cybernews.com/"),
                sitio("Dark Reading", "https://www.darkreading.com"),
                sitio("The Hacker News", "https://thehackernews.com/"),
                sitio("BleepingComputer", "https://www.bleepingcomputer.com/"),
                sitio("KrebsOnSecurity", "https://krebsonsecurity.com/"),
            ],
        },
        {
            "nombre": "Newspapers",
            "sitios": [
                sitio("MIT Technology Review", "https://www.technologyreview.com/"),
                sitio("Ethic", "https://ethic.es/"),
                sitio("Futuro.cl", "https://www.futuro.cl/"),
            ],
        },
        {
            "nombre": "Blogs",
            "sitios": [
                sitio("Schneier on Security", "https://www.schneier.com/"),
                sitio("elhacker.net", "https://elhacker.net/"),
            ],
        },
        {
            "nombre": "Privacidad y herramientas",
            "sitios": [
                sitio("PrivacyTools", "https://privacytools.io/es"),
                sitio("EFF", "https://www.eff.org/"),
                sitio("Privacy Guides", "https://www.privacyguides.org/posts/tag/articles/"),
                sitio("Matrix.org", "https://matrix.org/"),
                sitio("EDRi", "https://edri.org/"),
                sitio("The New Oil", "https://thenewoil.org/en/"),
                sitio("Tuta", "https://tuta.com/es/blog"),
                sitio("Cryptomator", "https://cryptomator.org/blog/"),
                sitio("Proton", "https://proton.me/es-419/blog"),
                sitio("Signal", "https://signal.org/blog/"),
                sitio("Ente", "https://ente.com/blog/"),
                sitio("Tor Project", "https://blog.torproject.org/"),
                sitio("Mastodon", "https://blog.joinmastodon.org/"),
                sitio("SimpleLogin", "https://simplelogin.io/blog/"),
                sitio("Quad9", "https://quad9.net/es/news/blog/"),
                sitio("Mullvad", "https://mullvad.net/es/blog"),
                sitio("Mozilla", "https://blog.mozilla.org/en/"),
                sitio("Bitwarden", "https://bitwarden.com/blog/"),
                sitio("Keep Android Open", "https://keepandroidopen.org/es/"),
                sitio("Fastmail", "https://www.fastmail.com/blog/"),
                sitio("Yubico", "https://www.yubico.com/blog/?lang=es"),
                sitio("Have I Been Pwned", "https://haveibeenpwned.com/"),
            ],
        },
    ],
    "vistos": [],
}

def descargar(url, timeout=10):

    peticion = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0 Safari/537.36"
            ),
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9,es;q=0.8"
        }
    )

    with urllib.request.urlopen(peticion, timeout=timeout) as respuesta:

        datos = respuesta.read()

        if respuesta.info().get("Content-Encoding") == "gzip":
            datos = gzip.decompress(datos)

        return datos

NS_MEDIA = "{http://search.yahoo.com/mrss/}"

NS_ATOM = "{http://www.w3.org/2005/Atom}"

def extraer_imagen_rss(item_el):

    enclosure = item_el.find("enclosure")

    if enclosure is not None and enclosure.get("url"):
        tipo = (enclosure.get("type") or "").lower()
        url = enclosure.get("url")
        if "image" in tipo or re.search(r"\.(jpg|jpeg|png|webp|gif)(?:[?#].*)?$", url, re.IGNORECASE):
            return url

    thumb = item_el.find(NS_MEDIA + "thumbnail")

    if thumb is not None and thumb.get("url"):
        return thumb.get("url")

    contenido_media = item_el.find(NS_MEDIA + "content")

    if contenido_media is not None and contenido_media.get("url"):
        tipo = (contenido_media.get("type") or "").lower()
        url = contenido_media.get("url")
        if "image" in tipo or re.search(r"\.(jpg|jpeg|png|webp|gif)(?:[?#].*)?$", url, re.IGNORECASE):
            return url

    desc_el = item_el.find("description")

    if desc_el is not None and desc_el.text:

        coincidencia = re.search(r'<img[^>]+(?:src|data-src)=["\']([^"\']+)["\']', desc_el.text, re.IGNORECASE)

        if coincidencia:
            return coincidencia.group(1)

    return None

def extraer_imagen_atom(entrada_el):

    for link_el in entrada_el.findall(NS_ATOM + "link"):

        if link_el.get("rel") == "enclosure" and "image" in (link_el.get("type") or ""):
            return link_el.get("href")

    thumb = entrada_el.find(NS_MEDIA + "thumbnail")

    if thumb is not None and thumb.get("url"):
        return thumb.get("url")

    return None

def parsear_feed(datos, maximo=ARTICULOS_POR_SITIO):

    raiz = ET.fromstring(datos)

    items = raiz.findall(".//item")

    if items:

        articulos = []

        for item in items[:maximo]:

            titulo_el = item.find("title")
            link_el = item.find("link")
            fecha_el = item.find("pubDate") or item.find("{http://purl.org/dc/elements/1.1/}date")

            titulo = (
                titulo_el.text.strip()
                if titulo_el is not None and titulo_el.text
                else "(sin título)"
            )

            link = (
                link_el.text.strip()
                if link_el is not None and link_el.text
                else ""
            )

            fecha = fecha_el.text.strip() if fecha_el is not None and fecha_el.text else ""
            imagen_contenido = guardar_contenido_feed(link, item)
            articulos.append((titulo, link, extraer_imagen_rss(item) or imagen_contenido, fecha))

        return articulos

    ns = {"atom": "http://www.w3.org/2005/Atom"}

    entradas = raiz.findall(".//atom:entry", ns)

    articulos = []

    for entrada in entradas[:maximo]:

        titulo_el = entrada.find("atom:title", ns)
        link_el = entrada.find("atom:link", ns)
        fecha_el = entrada.find("atom:published", ns) or entrada.find("atom:updated", ns)

        titulo = (
            titulo_el.text.strip()
            if titulo_el is not None and titulo_el.text
            else "(sin título)"
        )

        link = link_el.get("href") if link_el is not None else ""
        fecha = fecha_el.text.strip() if fecha_el is not None and fecha_el.text else ""
        imagen_contenido = guardar_contenido_feed(link, entrada)
        articulos.append((titulo, link, extraer_imagen_atom(entrada) or imagen_contenido, fecha))

    return articulos

def obtener_articulos(url_feed, silencioso=False, maximo=ARTICULOS_POR_SITIO):

    try:

        datos = descargar(url_feed)

        return parsear_feed(datos, maximo=maximo)

    except Exception as e:

        if not silencioso:
            print(f"[noticias] Error cargando {url_feed}: {e}")

        return None

def obtener_imagen_og(link):

    if not link:
        return None

    try:

        html = descargar(link, timeout=8).decode("utf-8", errors="ignore")

        parser = ContenidoHTML()
        parser.feed(html)
        if parser.imagen:
            return urllib.parse.urljoin(link, unescape(parser.imagen))

    except Exception:
        pass

    return None

def extraer_link_feed_de_html(html, base_url):

    etiquetas = re.findall(r"<link\b[^>]*>", html, re.IGNORECASE)

    for etiqueta in etiquetas:

        tipo_m = re.search(r'type=["\']([^"\']+)["\']', etiqueta, re.IGNORECASE)
        href_m = re.search(r'href=["\']([^"\']+)["\']', etiqueta, re.IGNORECASE)

        if not tipo_m or not href_m:
            continue

        tipo = tipo_m.group(1).lower()

        if "rss+xml" in tipo or "atom+xml" in tipo:
            return urllib.parse.urljoin(base_url, href_m.group(1))

    return None

RUTAS_COMUNES_DE_FEED = [
    "feed/", "feed", "rss/", "rss", "rss.xml", "atom.xml",
    "index.xml", ".rss", "feeds/posts/default", "blog/feed/",
    "blog/rss/", "blog/rss.xml", "en/feed/",
]

def descubrir_feed(url_sitio):

    try:

        html = descargar(url_sitio).decode("utf-8", errors="ignore")

        candidato = extraer_link_feed_de_html(html, url_sitio)

        if candidato and obtener_articulos(candidato, silencioso=True) is not None:
            return candidato

    except Exception as e:

        print(f"[noticias] No se pudo leer la portada de {url_sitio}: {e}")

    for sufijo in RUTAS_COMUNES_DE_FEED:

        candidato = urllib.parse.urljoin(url_sitio, sufijo)

        if obtener_articulos(candidato, silencioso=True) is not None:
            return candidato

    print(f"[noticias] No se encontró ningún feed para {url_sitio}")

    return None

def traducir_texto(texto, hacia="es"):

    try:

        parametros = urllib.parse.urlencode({
            "client": "gtx",
            "sl": "auto",
            "tl": hacia,
            "dt": "t",
            "q": texto
        })

        url = "https://translate.googleapis.com/translate_a/single?" + parametros

        peticion = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0"}
        )

        with urllib.request.urlopen(peticion, timeout=6) as respuesta:
            datos = json.loads(respuesta.read().decode("utf-8"))

        return "".join(fragmento[0] for fragmento in datos[0])

    except Exception:

        return None

def parsear_fecha_texto(valor):
    if not valor:
        return None

    valor = str(valor).strip()
    if not valor:
        return None

    try:
        return parsedate_to_datetime(valor)
    except Exception:
        pass

    try:
        return datetime.fromisoformat(valor.replace("Z", "+00:00"))
    except Exception:
        pass

    try:
        return datetime.strptime(valor, "%Y-%m-%d %H:%M:%S")
    except Exception:
        pass

    try:
        return datetime.strptime(valor, "%Y-%m-%d")
    except Exception:
        pass

    return None

def fecha_relativa(fecha):
    """Presenta una fecha del feed de manera breve y legible."""
    if fecha is None:
        return ""
    try:
        ahora = datetime.now(fecha.tzinfo) if fecha.tzinfo else datetime.now()
        segundos = max(0, int((ahora - fecha).total_seconds()))
    except Exception:
        return ""

    if segundos < 60:
        return "Ahora"
    if segundos < 3600:
        return f"Hace {segundos // 60} min"
    if segundos < 86400:
        return f"Hace {segundos // 3600} h"
    if segundos < 172800:
        return "Ayer"
    if segundos < 604800:
        return f"Hace {segundos // 86400} días"
    return fecha.strftime("%d %b %Y")

def crear_imagen_cita(fragmento, fuente, link, traducida=False, titulo="", color="#b9a0ff", imagen_bytes=None, idioma_original="", tema="gris") :
    """Genera una cita cuadrada con texto ajustado y atribución."""
    claro = tema == "periodico"
    imagen = Image.new("RGB", (1080, 1080), "#e6e6e6" if claro else "#171b20")
    dibujo = ImageDraw.Draw(imagen)
    ruta = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    def fuente_tamano(tamano):
        try:
            return ImageFont.truetype(ruta, tamano)
        except OSError:
            return ImageFont.load_default()
    def envolver(texto, font, ancho):
        lineas, linea = [], ""
        for palabra in texto.split():
            propuesta = (linea + " " + palabra).strip()
            if linea and dibujo.textlength(propuesta, font=font) > ancho:
                lineas.append(linea)
                linea = palabra
            else:
                linea = propuesta
        if linea:
            lineas.append(linea)
        return lineas
    try:
        titulo_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 30)
    except OSError:
        titulo_font = fuente_tamano(30)
    titulo_lineas = envolver(titulo, titulo_font, 880)
    division_titulo = 205 + len(titulo_lineas) * 40 + 16
    y_cita = division_titulo + 44
    if imagen_bytes:
        with Image.open(io.BytesIO(imagen_bytes)) as portada:
            imagen.paste(ImageOps.fit(portada.convert("RGB"), (880, 240)), (94, y_cita))
        y_cita += 266
    espacio = max(200, 885 - y_cita)
    for tamano in range(48, 15, -2):
        font = fuente_tamano(tamano)
        lineas = envolver(fragmento, font, 880)
        if len(lineas) * (tamano + 14) <= espacio and all(dibujo.textlength(l, font=font) <= 880 for l in lineas):
            break
    dibujo.rounded_rectangle((48, 48, 1032, 1032), radius=28, outline="#394453", width=2)
    dibujo.rectangle((94, 108, 150, 114), fill=color)
    dibujo.text((94, 145), "CITA EXTRAÍDA DEL ARTÍCULO", font=fuente_tamano(20), fill=color)
    dibujo.multiline_text((94, 205), "\n".join(titulo_lineas), font=titulo_font, fill=color, spacing=10)
    dibujo.line((94, division_titulo, 986, division_titulo), fill="#adadad" if claro else "#515b6a", width=2)
    dibujo.multiline_text((94, y_cita), "\n".join(lineas), font=font, fill="#202020" if claro else "#edf1f7", spacing=14)
    dibujo.line((94, 920, 986, 920), fill="#394453", width=2)
    idioma = {"en": "inglés", "es": "español"}.get(idioma_original)
    origen = "Versión original en " + idioma if idioma else "Versión original"
    atribucion = fuente[:45] + " · " + origen
    dibujo.text((94, 944), atribucion, font=fuente_tamano(18), fill="#202020" if claro else "#dbe1e9")
    dibujo.text((94, 978), urllib.parse.urlparse(link).netloc[:75], font=fuente_tamano(17), fill="#8793a3")
    imagen.info["articulo"] = link
    return imagen
