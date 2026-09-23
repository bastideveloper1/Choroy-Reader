import tkinter as tk
from tkinter import filedialog, messagebox
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import webbrowser
import threading
from biblioteca import Biblioteca, coincidencias, puntuar_radar
from concurrent.futures import ThreadPoolExecutor, as_completed
import subprocess
import re
import gzip
import json
import os
import time
from datetime import datetime
from email.utils import parsedate_to_datetime

try:
    from PIL import Image, ImageDraw, ImageOps, ImageFont
    import io
    PIL_DISPONIBLE = True
except ImportError:
    PIL_DISPONIBLE = False


def foto_tk(imagen):
    """Convierte Pillow a Tk sin depender del paquete opcional ImageTk."""
    buffer = io.BytesIO()
    imagen.save(buffer, format="PNG")
    return tk.PhotoImage(data=buffer.getvalue(), format="png")


from html.parser import HTMLParser
from html import unescape


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


# ============================================================
# CONFIGURACIÓN GUARDADA EN DISCO
# ============================================================

RUTA_CONFIG = os.path.expanduser("~/.config/noticias/config.json")

ARTICULOS_POR_SITIO = 3

MINUTOS_ENTRE_ACTUALIZACIONES = 30

ANCHO_MENU = 280

ANCHO_LECTURA = 420 + ANCHO_MENU

ANCHO_ADMIN = 640 + ANCHO_MENU

LOGO_PATHS = [
    os.path.expanduser("~/.config/noticias/assets/minimalfeedlogo.png"),
    os.path.expanduser("~/.config/noticias/logo/minimalfeedlogo.png"),
    os.path.expanduser("~/.config/noticias/minimalfeedlogo.png"),
    os.path.expanduser("~/.config/noticias/logo.png"),
    os.path.expanduser("~/minimalfeedlogo.png"),
    os.path.expanduser("~/minimalfeed-logo.png"),
    os.path.expanduser("~/logo.png"),
]

ancho_actual = ANCHO_LECTURA

logo_imagen = None
logo_idioma_imagen = None
icono_ventana_imagen = None
LOGO_SIZE = (64, 64)
LOGO_CABECERA_SIZE = (64, 64)
LOGO_IDIOMA_SIZE = (10, 10)

LOGOS_POR_TEMA = {
    "gris": "minimalfeedlogo_gris.png",
    "morado_neon": "minimalfeedlogo_lila.png",
    "azul_neon": "minimalfeedlogo_azul.png",
    "amarillo_neon": "minimalfeedlogo_amarillo.png",
    "verde_neon": "minimalfeedlogo_verde.png",
    "rosa_neon": "minimalfeedlogo_rosa.png",
}

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


def color_interfaz(color):
    if globals().get("config", {}).get("color", "gris") != "periodico":
        return color
    r, g, b = (int(color[i:i+2], 16) for i in (1, 3, 5))
    if max(r, g, b) - min(r, g, b) > 65:
        return color
    luminosidad = (r + g + b) / 3
    if luminosidad < 65:
        return "#e6e6e6" if luminosidad < 32 else "#d6d6d6"
    if luminosidad < 150:
        return "#62615c"
    return "#202020"


def recolorear_interfaz(widget):
    opciones = ("bg", "fg", "activebackground", "activeforeground", "highlightbackground", "insertbackground", "selectcolor", "troughcolor")
    originales = getattr(widget, "_colores_base", {})
    for opcion in opciones:
        try:
            valor = widget.cget(opcion)
            if opcion not in originales:
                originales[opcion] = {"#e6e6e6": "#171b20", "#d6d6d6": "#29313d", "#62615c": "#8793a3", "#202020": "#edf1f7"}.get(valor, valor)
            base = originales[opcion]
            if isinstance(base, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", base):
                widget.configure(**{opcion: color_interfaz(base)})
        except tk.TclError:
            pass
    widget._colores_base = originales
    for hijo in widget.winfo_children():
        recolorear_interfaz(hijo)


def tema_actual():
    if not isinstance(config, dict):
        return PALETA_TEMAS["gris"]

    tema = config.get("color") or config.get("tema") or "gris"
    if isinstance(tema, dict):
        tema = tema.get("nombre") or tema.get("valor") or "gris"

    nombre = str(tema).strip().lower()
    return PALETA_TEMAS.get(nombre, PALETA_TEMAS["gris"])


def aplicar_tema(nombre_tema):
    global paleta
    nombre = str(nombre_tema).strip().lower()
    if nombre not in PALETA_TEMAS:
        nombre = "gris"

    if config.get("color") != "periodico":
        recolorear_interfaz(ventana)
    config["tema"] = nombre
    config["color"] = nombre
    guardar_config()
    paleta = tema_actual()
    recolorear_interfaz(ventana)
    if "titulo_cabecera" in globals() and titulo_cabecera is not None:
        titulo_cabecera.config(fg=paleta["base"])
    if "cabecera_divider" in globals() and cabecera_divider is not None:
        cabecera_divider.config(bg=paleta["base"])
    if "logo_cabecera" in globals() and logo_cabecera is not None:
        actualizar_logo_cabecera(nombre)
    if "btn_diseño" in globals():
        actualizar_estado_botones_inferiores()
    if "marco_busqueda" in globals():
        marco_busqueda.event_generate("<Configure>")
    refrescar_vista_debounced()


def mostrar_titulo_traducido():
    return bool(config.get("mostrar_titulo_es", True))


def cargar_logo_app(nombre_tema=None, tamano=LOGO_SIZE):
    global logo_imagen
    ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "minimalfeed-logo.png")
    try:
        if PIL_DISPONIBLE:
            with Image.open(ruta) as archivo:
                imagen = ImageOps.contain(archivo.convert("RGBA"), tamano, method=Image.Resampling.LANCZOS)
            fondo = Image.new("RGBA", imagen.size, color_interfaz("#111315"))
            fondo.alpha_composite(imagen)
            logo_imagen = foto_tk(fondo.convert("RGB"))
        else:
            imagen = tk.PhotoImage(master=ventana, file=ruta)
            factor = max(1, (max(imagen.width(), imagen.height()) + max(tamano) - 1) // max(tamano))
            logo_imagen = imagen.subsample(factor, factor)
        return logo_imagen
    except Exception as error:
        print(f"[noticias] No se pudo cargar el logo {ruta}: {error}")
        return None


def actualizar_logo_cabecera(nombre_tema=None):
    imagen = cargar_logo_app(nombre_tema, LOGO_CABECERA_SIZE)
    # El propio widget conserva la referencia de Tk, incluso al cambiar de tema.
    logo_cabecera.image = imagen
    logo_cabecera.configure(image=imagen if imagen is not None else "",
                            text="MinimalFeed" if imagen is None else "")
    logo_cabecera.lift()


def cargar_logo_idioma(tamano=(22, 22)):
    global logo_idioma_imagen
    rutas = [
        os.path.expanduser("~/.config/noticias/assets/minimalfeedlogo_idioma.png"),
        os.path.expanduser("~/Descargas/minimalfeedlogo_idioma.png"),
    ]
    for ruta in rutas:
        if not os.path.isfile(ruta):
            continue
        try:
            if PIL_DISPONIBLE:
                imagen = Image.open(ruta).convert("RGBA")
                imagen = ImageOps.contain(imagen, tamano, method=Image.Resampling.LANCZOS)
                logo_idioma_imagen = foto_tk(imagen)
            else:
                logo_idioma_imagen = tk.PhotoImage(file=ruta)
            return logo_idioma_imagen
        except Exception:
            continue
    logo_idioma_imagen = None
    return None


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


def mostrar_titulo_traducido_sitio(sitio_actual):
    if not isinstance(sitio_actual, dict):
        return False
    if not mostrar_titulo_traducido():
        return False
    modo = sitio_actual.get("modo_titulo", "en_es")
    if modo == "solo_ingles":
        return False
    return bool(sitio_actual.get("traduccion_es", True))


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


def cargar_config():

    if os.path.isfile(RUTA_CONFIG):

        try:

            with open(RUTA_CONFIG, "r", encoding="utf-8") as f:
                datos = json.load(f)

            if isinstance(datos, dict) and isinstance(datos.get("categorias"), list):
                if "tema" not in datos:
                    datos["tema"] = CONFIG_INICIAL["tema"]
                if "color" not in datos:
                    datos["color"] = datos.get("tema", CONFIG_INICIAL["color"])
                if "mostrar_titulo_es" not in datos:
                    datos["mostrar_titulo_es"] = CONFIG_INICIAL.get("mostrar_titulo_es", True)
                if "articulos_por_fila" not in datos:
                    datos["articulos_por_fila"] = CONFIG_INICIAL.get("articulos_por_fila", 5)

                datos["tema"] = datos.get("color") or datos.get("tema") or CONFIG_INICIAL["tema"]
                datos["color"] = datos["tema"]
                datos["mostrar_titulo_es"] = bool(datos.get("mostrar_titulo_es", True))
                try:
                    columnas = int(datos.get("articulos_por_fila", CONFIG_INICIAL.get("articulos_por_fila", 5)))
                    if columnas not in {1, 2, 3, 4, 5}:
                        raise ValueError
                    datos["articulos_por_fila"] = columnas
                except Exception:
                    datos["articulos_por_fila"] = CONFIG_INICIAL.get("articulos_por_fila", 5)

                for categoria in datos["categorias"]:
                    if isinstance(categoria, dict):
                        categoria.pop("imagen", None)
                        for sitio_actual in categoria.get("sitios", []):
                            if isinstance(sitio_actual, dict):
                                sitio_actual.setdefault("modo_titulo", "en_es" if bool(datos.get("mostrar_titulo_es", True)) else "solo_ingles")
                                sitio_actual.setdefault("traduccion_es", True)
                                if sitio_actual.get("modo_titulo") not in {"solo_ingles", "en_es"}:
                                    sitio_actual["modo_titulo"] = "en_es"
                                sitio_actual["traduccion_es"] = bool(sitio_actual.get("traduccion_es", True))

                # Activamos una vez las imágenes de vista previa para que las
                # tarjetas puedan revelar la portada del artículo al pasar el mouse.
                if not datos.get("imagenes_hover_activadas", False):
                    for categoria in datos["categorias"]:
                        for sitio_actual in categoria.get("sitios", []):
                            if isinstance(sitio_actual, dict):
                                sitio_actual["mostrar_imagen"] = True
                    datos["imagenes_hover_activadas"] = True

                nombres_existentes = {c.get("nombre") for c in datos["categorias"] if isinstance(c, dict) and c.get("nombre")}

                for categoria_default in CONFIG_INICIAL["categorias"]:
                    nombre = categoria_default.get("nombre")
                    if nombre not in nombres_existentes:
                        datos["categorias"].append(json.loads(json.dumps(categoria_default)))

            return datos

        except Exception as e:

            print(f"[noticias] No se pudo leer la config, uso la inicial: {e}")

    return json.loads(json.dumps(CONFIG_INICIAL))


def guardar_config():

    try:

        os.makedirs(os.path.dirname(RUTA_CONFIG), exist_ok=True)

        with open(RUTA_CONFIG, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

    except Exception as e:

        print(f"[noticias] No se pudo guardar la config: {e}")


config = cargar_config()
biblioteca = Biblioteca(os.path.join(os.path.dirname(RUTA_CONFIG), "biblioteca"))
textos_articulos = {}
descargas_en_curso = set()
radar_en_curso = False
busqueda_titulos = ""


vistos = set(config.get("vistos", []))


# ============================================================
# DESCARGA Y PARSEO DE FEEDS (RSS y Atom)
# ============================================================

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


# ============================================================
# DESCUBRIR EL FEED A PARTIR DE LA PORTADA DE UN SITIO
# ============================================================

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


# ============================================================
# FAVICONS E IMÁGENES
# ============================================================

CARPETA_FAVICONS = os.path.expanduser("~/.config/noticias/favicons")
CARPETA_ICONOS = os.path.expanduser("~/.config/noticias/icons")
TAMANO_FAVICON = 10
TAMANO_MINIATURA = 64
TAMANO_ICONO_BOTON = 18

referencias_imagenes_articulos = []  # evita que Tkinter borre las miniaturas de la memoria
iconos_botones_cache = {}  # cache para iconos SVG convertidos


def dibujar_icono_simple(tipo, color="#d4d9de", tamano=18):
    """Dibuja iconos simples usando PIL sin dependencias externas"""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None
    
    cache_key = f"{tipo}_{color}_{tamano}"
    if cache_key in iconos_botones_cache:
        return iconos_botones_cache[cache_key]
    
    try:
        # Crear imagen transparente
        imagen = Image.new("RGBA", (tamano, tamano), (0, 0, 0, 0))
        draw = ImageDraw.Draw(imagen)
        
        # Convertir color hex a RGB (agregar alpha 255)
        color_rgb = tuple(int(color.lstrip('#')[i:i+2], 16) for i in (0, 2, 4)) + (255,)
        
        centro = tamano // 2
        grosor = 2
        
        if tipo == "refresh":
            # Flecha de rotación
            draw.arc([2, 2, tamano-2, tamano-2], 0, 270, fill=color_rgb, width=grosor)
            # Flecha
            draw.polygon([tamano-4, centro, tamano-8, centro-3, tamano-8, centro+3], fill=color_rgb)
            
        elif tipo == "newspaper":
            # Documento con líneas
            draw.rectangle([3, 2, tamano-3, tamano-4], outline=color_rgb, width=grosor)
            draw.line([6, 6, tamano-6, 6], fill=color_rgb, width=grosor)
            draw.line([6, 10, tamano-10, 10], fill=color_rgb, width=grosor)
            draw.line([6, 14, tamano-8, 14], fill=color_rgb, width=grosor)
            
        elif tipo == "palette":
            # Paleta de colores simple
            draw.ellipse([centro-2, centro-6, centro+2, centro-2], fill=color_rgb)
            draw.ellipse([centro-4, centro, centro, centro+4], fill=color_rgb)
            draw.ellipse([centro+2, centro-4, centro+6, centro], fill=color_rgb)
            
        elif tipo == "folder":
            # Carpeta
            draw.polygon([2, 6, 2, tamano-4, tamano-2, tamano-4, tamano-2, 10, centro, 6], outline=color_rgb, width=grosor)
            
        elif tipo == "link":
            # Enlace simple
            draw.line([4, centro, tamano-4, centro], fill=color_rgb, width=grosor)
            draw.line([tamano-6, centro-3, tamano-2, centro], fill=color_rgb, width=grosor)
            draw.line([tamano-6, centro+3, tamano-2, centro], fill=color_rgb, width=grosor)
        
        foto = foto_tk(imagen)
        iconos_botones_cache[cache_key] = foto
        return foto
        
    except Exception as e:
        print(f"[noticias] Error dibujando icono {tipo}: {e}")
        return None


def ruta_favicon_cache(dominio):

    os.makedirs(CARPETA_FAVICONS, exist_ok=True)

    nombre_archivo = re.sub(r"[^a-zA-Z0-9]", "_", dominio) + ".png"

    return os.path.join(CARPETA_FAVICONS, nombre_archivo)


def descargar_favicon(url_sitio):

    dominio = urllib.parse.urlparse(url_sitio).netloc
    ruta = ruta_favicon_cache(dominio)

    if os.path.isfile(ruta):
        return ruta

    try:

        favicon_url = f"https://www.google.com/s2/favicons?sz=32&domain={dominio}"
        datos = descargar(favicon_url, timeout=8)

        with open(ruta, "wb") as f:
            f.write(datos)

        return ruta

    except Exception as e:

        print(f"[noticias] No se pudo obtener el favicon de {dominio}: {e}")

        return None


def redimensionar_favicon(ruta_origen, ruta_destino):

    try:

        if PIL_DISPONIBLE:

            imagen = Image.open(ruta_origen).convert("RGBA")
            imagen.thumbnail((TAMANO_FAVICON, TAMANO_FAVICON), Image.Resampling.LANCZOS)

            lienzo = Image.new("RGBA", (TAMANO_FAVICON, TAMANO_FAVICON), (0, 0, 0, 0))
            x = (TAMANO_FAVICON - imagen.width) // 2
            y = (TAMANO_FAVICON - imagen.height) // 2
            lienzo.paste(imagen, (x, y), imagen)
            lienzo.save(ruta_destino, "PNG")
            return True

        # Fallback para PNG/GIF si Pillow no está disponible.
        imagen = tk.PhotoImage(file=ruta_origen)
        factor = max(1, max(imagen.width(), imagen.height()) // TAMANO_FAVICON)
        if factor > 1:
            imagen = imagen.subsample(factor, factor)
        imagen.write(ruta_destino, format="png")
        return True

    except Exception as e:

        print(f"[noticias] No se pudo redimensionar el favicon: {e}")
        return False


rutas_favicon = {}             # url del sitio -> ruta del archivo del icono
imagenes_favicon_cache = {}    # url del sitio -> objeto PhotoImage ya cargado


def obtener_ruta_favicon(sitio_actual):

    personalizado = sitio_actual.get("favicon_personalizado")

    if personalizado and os.path.isfile(personalizado):
        return personalizado

    return rutas_favicon.get(sitio_actual["url"])


def obtener_imagen_favicon(sitio_actual):

    url_sitio = sitio_actual["url"]

    if url_sitio in imagenes_favicon_cache:
        return imagenes_favicon_cache[url_sitio]

    ruta = obtener_ruta_favicon(sitio_actual)

    if not ruta:
        return None

    try:

        if PIL_DISPONIBLE:
            imagen = Image.open(ruta).convert("RGBA")
            imagen.thumbnail((TAMANO_FAVICON, TAMANO_FAVICON), Image.Resampling.LANCZOS)
            foto = foto_tk(imagen)
        else:
            foto = tk.PhotoImage(file=ruta)

            # Si Pillow no está instalado, reducimos la imagen con subsample
            try:
                factor = max(1, max(foto.width(), foto.height()) // TAMANO_FAVICON)
                if factor > 1:
                    foto = foto.subsample(factor, factor)
            except Exception:
                pass

        imagenes_favicon_cache[url_sitio] = foto
        return foto

    except Exception:

        return None


def cargar_miniatura(imagen_bytes, tamano=None):

    if not imagen_bytes:
        return None, None, None

    target = tamano or TAMANO_MINIATURA

    try:
        if PIL_DISPONIBLE:
            imagen = Image.open(io.BytesIO(imagen_bytes)).convert("RGB")
            ancho_original, alto_original = imagen.size
            imagen.thumbnail((target, target), Image.Resampling.LANCZOS)
            foto = foto_tk(imagen)
        else:
            foto = tk.PhotoImage(data=imagen_bytes)
            ancho_original = foto.width()
            alto_original = foto.height()
            factor = max(1, max(foto.width(), foto.height()) // target)
            if factor > 1:
                foto = foto.subsample(factor, factor)

        referencias_imagenes_articulos.append(foto)
        return foto, ancho_original, alto_original
    except Exception:
        return None, None, None


def cargar_miniatura_cubierta(imagen_bytes, ancho, alto):
    """Prepara una imagen para cubrir una tarjeta sin deformarla."""
    if not imagen_bytes or not PIL_DISPONIBLE:
        return None

    try:
        imagen = Image.open(io.BytesIO(imagen_bytes)).convert("RGB")
        destino_ancho, destino_alto = max(1, ancho), max(1, alto)
        escala = max(destino_ancho / imagen.width, destino_alto / imagen.height)
        ancho_redimensionado = max(destino_ancho, round(imagen.width * escala))
        alto_redimensionado = max(destino_alto, round(imagen.height * escala))
        imagen = imagen.resize((ancho_redimensionado, alto_redimensionado), Image.Resampling.LANCZOS)
        izquierda = (ancho_redimensionado - destino_ancho) // 2
        arriba = (alto_redimensionado - destino_alto) // 2
        cubierta = imagen.crop((izquierda, arriba, izquierda + destino_ancho, arriba + destino_alto))
        foto = foto_tk(cubierta)
        referencias_imagenes_articulos.append(foto)
        return foto
    except Exception as error:
        print(f"[noticias] No se pudo preparar la imagen de la tarjeta: {error}")
        return None


def crear_preview_diagonal(padre, imagen, ancho, alto, fuente, titulo, subtitulo=""):
    """Crea una tarjeta editorial: texto a la izquierda e imagen a la derecha."""
    preview = tk.Canvas(
        padre, width=ancho, height=alto, bg="#171717",
        highlightthickness=0, bd=0
    )
    preview.create_image(0, 0, image=imagen, anchor="nw")
    preview.image = imagen

    corte_superior = int(ancho * 0.63)
    corte_inferior = int(ancho * 0.43)
    preview.create_polygon(
        0, 0, corte_superior, 0, corte_inferior, alto, 0, alto,
        fill="#111315", outline=""
    )
    preview.create_text(
        14, 14, text=fuente.upper(), anchor="nw", width=max(80, corte_inferior - 24),
        fill=paleta["base_fuerte"], font=("Sans", 7, "bold")
    )
    preview.create_text(
        14, 38, text=titulo, anchor="nw", width=max(80, corte_inferior - 28),
        fill="#f4f5f7", font=("Sans", 8, "bold"), justify="left"
    )
    if subtitulo:
        preview.create_text(
            14, max(78, int(alto * 0.54)), text=subtitulo, anchor="nw",
            width=max(80, corte_inferior - 28), fill="#b7bec9",
            font=("Sans", 7), justify="left"
        )
    return preview


def guardar_favicon_personalizado(sitio_actual, ruta_origen):

    if not ruta_origen or not os.path.isfile(ruta_origen):
        return False

    os.makedirs(CARPETA_FAVICONS, exist_ok=True)

    dominio = urllib.parse.urlparse(sitio_actual["url"]).netloc
    nombre = re.sub(r"[^a-zA-Z0-9]", "_", dominio) or "sitio"
    ruta_destino = os.path.join(CARPETA_FAVICONS, f"{nombre}_personalizado.png")

    if not redimensionar_favicon(ruta_origen, ruta_destino):
        return False

    sitio_actual["favicon_personalizado"] = ruta_destino
    imagenes_favicon_cache.pop(sitio_actual["url"], None)
    guardar_config()
    return True


def seleccionar_favicon_personalizado(sitio_actual):

    if not PIL_DISPONIBLE:
        messagebox.showinfo(
            "Pillow necesario",
            "Para subir imágenes JPG/JPEG/WebP como favicon instala Pillow:\n\n"
            "sudo apt install python3-pil python3-pil.imagetk"
        )
        return

    ruta = filedialog.askopenfilename(
        title="Seleccionar favicon",
        filetypes=[
            ("Imágenes", "*.png *.jpg *.jpeg *.webp *.gif *.bmp"),
            ("Todos los archivos", "*.*")
        ]
    )

    if not ruta:
        return

    if guardar_favicon_personalizado(sitio_actual, ruta):
        vista_admin()
    else:
        messagebox.showerror("Favicon", "No se pudo cargar esa imagen.")


def quitar_favicon_personalizado(sitio_actual):

    ruta = sitio_actual.get("favicon_personalizado")

    if ruta and os.path.isfile(ruta):
        try:
            os.remove(ruta)
        except OSError:
            pass

    sitio_actual["favicon_personalizado"] = None
    imagenes_favicon_cache.pop(sitio_actual["url"], None)
    guardar_config()
    vista_admin()


# ============================================================
# TRADUCCIÓN DE TÍTULOS (servicio gratuito no oficial)
# ============================================================

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


# ============================================================
# POSICIÓN (abajo a la izquierda del monitor principal)
# ============================================================

def obtener_monitor_principal():

    try:

        resultado = subprocess.run(
            ["xrandr", "--query"],
            capture_output=True,
            text=True
        )

        for linea in resultado.stdout.splitlines():

            if " connected primary " not in linea:
                continue

            coincidencia = re.search(
                r"(\d+)x(\d+)\+(-?\d+)\+(-?\d+)",
                linea
            )

            if coincidencia:

                ancho = int(coincidencia.group(1))
                alto = int(coincidencia.group(2))
                x = int(coincidencia.group(3))
                y = int(coincidencia.group(4))

                return (ancho, alto, x, y)

    except Exception:

        pass

    return None


def posicionar_abajo_izquierda():

    ventana.update_idletasks()

    alto_ventana = ventana.winfo_height()

    monitor = obtener_monitor_principal()

    if monitor is not None:

        _, pantalla_alto, pantalla_x, pantalla_y = monitor

    else:

        pantalla_alto = ventana.winfo_screenheight()
        pantalla_x, pantalla_y = 0, 0

    x = pantalla_x + 10
    y = pantalla_y + pantalla_alto - alto_ventana - 10

    ventana.geometry(f"+{x}+{y}")


# ============================================================
# VENTANA
# ============================================================

ventana = tk.Tk()
ventana.title("MinimalFeed")
ventana.iconname("MinimalFeed")

try:
    icono_ventana_imagen = tk.PhotoImage(
        file=os.path.expanduser("~/.config/noticias/assets/iconoescritorio.png")
    )
    ventana.iconphoto(True, icono_ventana_imagen)
except Exception as error:
    print(f"[noticias] No se pudo cargar el icono de la ventana: {error}")

# Mostrar decoraciones/entrada en la barra de tareas (no usar overrideredirect al inicio)
ventana.overrideredirect(False)

ventana.attributes("-topmost", True)

ventana.configure(bg=color_interfaz("#0c0d10"))

ventana.geometry(f"{ancho_actual}x500")
ventana.minsize(ANCHO_LECTURA, min(620, ventana.winfo_screenheight() - 100))


carcasa = tk.Frame(
    ventana,
    bg=color_interfaz("#111315"),
    highlightbackground=color_interfaz("#2a2e34"),
    highlightthickness=2
)

carcasa.pack(fill="both", expand=True)


def ajustar_alto_auto():

    ventana.update_idletasks()

    contenido_alto = contenido.winfo_reqheight()

    monitor = obtener_monitor_principal()

    if monitor is not None:
        _, pantalla_alto, _, _ = monitor
    else:
        pantalla_alto = ventana.winfo_screenheight()

    max_alto_ventana = int(pantalla_alto * FRACCION_ALTO_MAXIMO)

    chrome = cabecera.winfo_reqheight() + 36

    # El panel conserva un alto útil incluso al mostrar una fuente vacía.
    deseado_total = max(480, contenido_alto + 20) + chrome

    if deseado_total <= max_alto_ventana:

        scrollbar.pack_forget()

        alto_final = deseado_total

    else:

        scrollbar.pack(side="right", fill="y", before=canvas)

        alto_final = max_alto_ventana

    x = ventana.winfo_x()
    y = ventana.winfo_y()

    if not fullscreen:
        ancho_ventana = max(ancho_actual, ventana.winfo_width())
        ventana.geometry(f"{ancho_ventana}x{alto_final}+{x}+{y}")

    ventana.update_idletasks()

    canvas.configure(scrollregion=canvas.bbox("all"))


# ============================================================
# CABECERA (arrastrable + administrar + actualizar + cerrar)
# ============================================================

cabecera = tk.Frame(carcasa, bg=color_interfaz("#111315"), height=84)

cabecera.pack(fill="x", padx=8, pady=(8, 8))

cabecera.pack_propagate(False)

paleta = tema_actual()
logo_cabecera = tk.Label(cabecera, bg=color_interfaz("#111315"), fg=paleta["texto"], bd=0)
logo_cabecera.place(x=8, y=8, width=64, height=64)
actualizar_logo_cabecera()

titulo_cabecera = tk.Label(
    cabecera,
    text="Tus fuentes. Tu feed. Sin distracciones.",
    font=("Inter", 11, "bold"),
    fg=paleta["base"],
    bg=color_interfaz("#111315"),
    cursor="fleur"
)
titulo_cabecera.pack(side="top", padx=(86, 6), pady=(12, 0), anchor="center")

cabecera_subrayado = tk.Frame(cabecera, bg=color_interfaz("#111315"), height=1)
cabecera_subrayado.pack(anchor="center", pady=(4, 0))

cabecera_divider = tk.Label(
    cabecera,
    text="",
    bg=paleta["base"],
    width=12,
    height=1,
    anchor="center"
)
cabecera_divider.pack(anchor="center", pady=(0, 6))

fullscreen = False
prev_geometry = None


def alternar_fullscreen(event=None):

    global fullscreen, prev_geometry

    try:
        if not fullscreen:
            # entrar en fullscreen: guardamos geometría y permitimos al WM gestionar
            prev_geometry = ventana.geometry()
            try:
                ventana.overrideredirect(False)
            except Exception:
                pass
            ventana.attributes("-fullscreen", True)
            fullscreen = True
        else:
            # salir de fullscreen: devolvemos decorations y geometría previa
            ventana.attributes("-fullscreen", False)
            try:
                ventana.overrideredirect(True)
            except Exception:
                pass
            if prev_geometry:
                try:
                    ventana.geometry(prev_geometry)
                except Exception:
                    pass
            posicionar_abajo_izquierda()
            fullscreen = False
    except Exception:
        pass



# Dos columnas: navegación lateral y área de lectura independiente.
cuerpo_principal = tk.Frame(carcasa, bg=color_interfaz("#111315"))
cuerpo_principal.pack(fill="both", expand=True)
area_lectura = tk.Frame(cuerpo_principal, bg=color_interfaz("#111315"))
area_lectura.pack(side="left", fill="both", expand=True)

menu_lateral = tk.Frame(cuerpo_principal, bg=color_interfaz("#191d23"), width=ANCHO_MENU,
                       highlightthickness=0)
menu_lateral.pack(side="left", fill="y", before=area_lectura)
menu_lateral.pack_propagate(False)

barra_opciones = tk.Frame(menu_lateral, bg=color_interfaz("#191d23"))
barra_opciones.pack(fill="x", padx=12, pady=(16, 12))

contenedor_botones = tk.Frame(barra_opciones, bg=color_interfaz("#191d23"))
contenedor_botones.pack(fill="x")

actualizar_btn = tk.Label(
    contenedor_botones, text="", font=("Inter", 9),
    fg=color_interfaz("#d4d9de"), bg=color_interfaz("#191d23"), cursor="hand2",
    anchor="w", padx=12, pady=10, borderwidth=0, relief="flat"
)
actualizar_btn.pack(fill="x", pady=2)
actualizar_btn.bind("<Enter>", lambda event: actualizar_btn.config(fg=color_interfaz("#ffffff")))
actualizar_btn.bind("<Leave>", lambda event: actualizar_btn.config(fg=color_interfaz("#d4d9de")))

btn_principal = tk.Label(
    contenedor_botones, text="Feed", font=("Inter", 8),
    fg=color_interfaz("#d4d9de"), bg=color_interfaz("#191d23"), cursor="hand2",
    anchor="w", padx=12, pady=10, borderwidth=0, relief="flat"
)
btn_principal.pack(fill="x", pady=2)
btn_principal.bind("<Enter>", lambda event: btn_principal.config(fg=paleta["base_fuerte"]))
btn_principal.bind("<Leave>", lambda event: actualizar_color_btn_principal(btn_principal, "feed"))
btn_principal.bind("<Button-1>", lambda event: ir_a_principal())


btn_diseño = tk.Label(
    contenedor_botones, text="", font=("Inter", 14),
    fg=color_interfaz("#d4d9de"), bg=color_interfaz("#191d23"), cursor="hand2",
    anchor="w", padx=12, pady=10, borderwidth=0, relief="flat"
)
btn_diseño.pack(fill="x", pady=2)
btn_diseño.bind("<Enter>", lambda event: btn_diseño.config(fg=paleta["base_fuerte"]))
btn_diseño.bind("<Leave>", lambda event: actualizar_color_btn_principal(btn_diseño, "diseño"))
btn_diseño.bind("<Button-1>", lambda event: ir_a_diseño())


btn_categorias = tk.Label(
    contenedor_botones, text="", font=("Inter", 14),
    fg=color_interfaz("#d4d9de"), bg=color_interfaz("#191d23"), cursor="hand2",
    anchor="w", padx=12, pady=10, borderwidth=0, relief="flat"
)
btn_categorias.pack(fill="x", pady=2)
btn_categorias.bind("<Enter>", lambda event: btn_categorias.config(fg=paleta["base_fuerte"]))
btn_categorias.bind("<Leave>", lambda event: actualizar_color_btn_principal(btn_categorias, "categorias"))
btn_categorias.bind("<Button-1>", lambda event: ir_a_categorias())

for boton_opcion in (actualizar_btn, btn_principal, btn_diseño, btn_categorias):
    boton_opcion.bind("<Enter>", lambda event: event.widget.config(bg=color_interfaz("#2b323c")), add="+")
    boton_opcion.bind("<Leave>", lambda event: event.widget.config(bg=color_interfaz("#191d23")), add="+")

def actualizar_icono_btn(tipo, color):
    """Actualiza el icono de un botón con el color especificado"""
    icono = dibujar_icono_simple(tipo, color)
    if icono:
        if tipo == "actualizar":
            actualizar_btn.config(image=icono)
            actualizar_btn.image = icon
        elif tipo == "principal":
            btn_principal.config(image=icono)
            btn_principal.image = icon
        elif tipo == "diseño":
            btn_diseño.config(image=icono)
            btn_diseño.image = icon
        elif tipo == "categorias":
            btn_categorias.config(image=icono)
            btn_categorias.image = icon


def cargar_iconos_botones():
    """Muestra las opciones de navegación en la barra lateral."""
    actualizar_btn.config(text="Actualizar feed", font=("Inter", 8))
    btn_principal.config(text="Feed", font=("Inter", 8))
    btn_diseño.config(text="Diseño", font=("Inter", 8))
    btn_categorias.config(text="Fuentes/Categorías", font=("Inter", 8))


def actualizar_estado_botones_inferiores():
    # La sección activa conserva el color del tema; las demás quedan atenuadas.
    actualizar_color_btn_principal(btn_principal, "feed")
    actualizar_color_btn_principal(btn_diseño, "diseño")
    actualizar_color_btn_principal(btn_categorias, "categorias")

def actualizar_color_btn_principal(btn, seccion):
    if (seccion == "feed" and not modo_admin) or \
       (seccion == "diseño" and modo_admin and seccion_config == "diseño") or \
       (seccion == "categorias" and modo_admin and seccion_config == "categorias") or \
       (seccion == "fuentes" and modo_admin and seccion_config == "fuentes"):
        btn.config(fg=paleta["base"])
    else:
        btn.config(fg=color_interfaz("#7a8592"))

def ir_a_principal():
    global lector_activo
    lector_activo = None
    navegar_menu()


def ir_a_diseño():
    global modo_admin, seccion_config
    modo_admin = True
    seccion_config = "diseño"
    actualizar_estado_botones_inferiores()
    refrescar_vista_con_carga(lambda: refrescar_vista())

def ir_a_categorias():
    global modo_admin, seccion_config
    modo_admin = True
    seccion_config = "categorias"
    actualizar_estado_botones_inferiores()
    refrescar_vista_con_carga(lambda: refrescar_vista())

def ir_a_fuentes():
    global modo_admin, seccion_config
    modo_admin = True
    seccion_config = "fuentes"
    actualizar_estado_botones_inferiores()
    refrescar_vista_con_carga(lambda: refrescar_vista())


arrastre_x = 0
arrastre_y = 0


def iniciar_arrastre(event):

    global arrastre_x, arrastre_y

    arrastre_x = event.x_root - ventana.winfo_x()
    arrastre_y = event.y_root - ventana.winfo_y()


def mover_ventana(event):

    x = event.x_root - arrastre_x
    y = event.y_root - arrastre_y

    ventana.geometry(f"+{x}+{y}")


def forzar_foco(widget):

    try:

        subprocess.run(
            ["xdotool", "windowfocus", str(ventana.winfo_id())],
            capture_output=True,
            timeout=1
        )

    except Exception:

        pass

    ventana.focus_force()
    widget.focus_set()


for widget in [cabecera] + ([titulo_cabecera] if titulo_cabecera is not None else []):
    widget.bind("<ButtonPress-1>", iniciar_arrastre)
    widget.bind("<B1-Motion>", mover_ventana)


# ============================================================
# CONTENIDO (dentro de un Canvas con scrollbar discreta)
# ============================================================

FRACCION_ALTO_MAXIMO = 0.8  # nunca ocupa más del 80% de la pantalla

area_desplazable = tk.Frame(area_lectura, bg=color_interfaz("#111315"))

area_desplazable.pack(fill="both", expand=True)

canvas = tk.Canvas(
    area_desplazable, bg=color_interfaz("#111315"), highlightthickness=0, bd=0
)

scrollbar = tk.Scrollbar(
    area_desplazable, orient="vertical", command=canvas.yview,
    width=8, troughcolor=color_interfaz("#111315"), bg=color_interfaz("#3d434b"),
    activebackground=color_interfaz("#6e7c8b"), highlightthickness=0, bd=0
)

canvas.configure(yscrollcommand=scrollbar.set)

canvas.pack(side="left", fill="both", expand=True, padx=10, pady=(12, 8))

contenido = tk.Frame(canvas, bg=color_interfaz("#111315"))

contenido_id = canvas.create_window((0, 0), window=contenido, anchor="nw")


def _sincronizar_ancho_contenido(event):
    canvas.itemconfig(contenido_id, width=event.width)


canvas.bind("<Configure>", _sincronizar_ancho_contenido)


def _rueda_arriba(event):
    canvas_rueda(event).yview_scroll(-3, "units")


def _rueda_abajo(event):
    canvas_rueda(event).yview_scroll(3, "units")


def canvas_rueda(event):
    widget = event.widget
    if isinstance(widget, tk.Text):
        return widget
    while widget is not None:
        if widget is menu_lateral:
            return canvas_menu
        widget = getattr(widget, "master", None)
    return canvas


canvas.bind_all("<Button-4>", _rueda_arriba)
canvas.bind_all("<Button-5>", _rueda_abajo)



def limpiar_contenido():
    # Las tarjetas se destruyen al cambiar de vista; no conservamos una
    # referencia a una tarjeta anterior para el resaltado del cursor.
    global tarjeta_hover_actual
    tarjeta_hover_actual = None

    for widget in contenido.winfo_children():
        widget.destroy()


# ============================================================
# ESTADO DE LECTURA
# ============================================================

expandido_categoria = {}

expandido_sitio = {}

vista_actual = "categorias"

categoria_activa = None

fuente_activa = None
categorias_menu_expandidas = set()

filtro_principal = "todo"

ui_refresh_pending = False

preview_activo = None

MAX_ARTICULOS_PREVIEW = 4

datos_articulos = {}   # url del sitio -> artículos normalizados | None | "cargando"

modo_admin = False

seccion_config = "diseño"  # "diseño", "categorias", "fuentes"

minimizado = False

mini_ventana = None

mini_etiqueta = None


def contar_no_leidos(articulos):

    if not articulos or articulos == "cargando":
        return 0

    return sum(1 for item in articulos if isinstance(item, (tuple, list)) and item and item[1] and item[1] not in vistos)


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


def columnas_para_ancho(ancho):
    valor = config.get("articulos_por_fila")
    try:
        columnas = int(valor)
        if columnas in {1, 2, 3, 4, 5}:
            # La preferencia es un máximo. En una ventana pequeña reducimos
            # columnas para no comprimir ni desbordar las tarjetas.
            columnas_posibles = max(1, (ancho - 24) // 210)
            return min(columnas, columnas_posibles)
    except Exception:
        pass

    if ancho >= 1800:
        return 4
    if ancho >= 1400:
        return 3
    if ancho >= 1000:
        return 2
    return 1


def estilo_tarjeta_por_columnas(columnas):
    mapa = {
        5: {"titulo": 7, "traducido": 7, "fuente": 6, "alto": 180, "miniatura": 110},
        4: {"titulo": 8, "traducido": 8, "fuente": 7, "alto": 200, "miniatura": 140},
        3: {"titulo": 9, "traducido": 9, "fuente": 7, "alto": 220, "miniatura": 160},
        2: {"titulo": 10, "traducido": 10, "fuente": 8, "alto": 240, "miniatura": 180},
        1: {"titulo": 11, "traducido": 11, "fuente": 8, "alto": 280, "miniatura": 200},
    }
    return mapa.get(columnas, mapa[3])


def preparar_preview_imagen(envoltorio, contenedor, label_texto, label_texto_extra, label_imagen, color_normal, color_hover, link=None, label_id=None):
    estado_hover = {"activo": False, "ocultar_id": None, "animacion": 0}

    def aplicar_colores(visibilidad):
        try:
            if label_texto is not None and label_texto.winfo_exists():
                label_texto.configure(fg=color_hover if visibilidad else color_normal)
            if label_texto_extra is not None and label_texto_extra.winfo_exists():
                label_texto_extra.configure(fg=color_interfaz("#9aa4b2") if visibilidad else (color_interfaz("#aaaaaa") if label_id is None else color_interfaz("#aaaaaa")))
        except Exception:
            pass

    def animar(mostrar):
        if label_imagen is None:
            return
        
        if not label_imagen.winfo_exists():
            return

        try:
            ancho_contenedor = contenedor.winfo_width()
            alto_contenedor = contenedor.winfo_height()
        except Exception:
            ancho_contenedor = 180
            alto_contenedor = 100

        estado_hover["animacion"] += 1
        animacion_actual = estado_hover["animacion"]

        if mostrar:
            # La portada editorial se presenta completa; evita el antiguo efecto
            # de miniatura que se expandía desde el centro.
            label_imagen.place(in_=contenedor, x=0, y=0, width=ancho_contenedor, height=alto_contenedor)
            label_imagen.lift()
            if label_texto is not None and label_texto.winfo_exists():
                label_texto.pack_forget()
            if label_texto_extra is not None and label_texto_extra.winfo_exists():
                label_texto_extra.pack_forget()
            aplicar_colores(True)
        else:
            if label_texto is not None and label_texto.winfo_exists():
                label_texto.pack(anchor="w")
            if label_texto_extra is not None and label_texto_extra.winfo_exists():
                label_texto_extra.pack(anchor="w", pady=(2, 0))
            label_imagen.place_forget()
            aplicar_colores(False)

    def mostrar_preview(event=None):
        global preview_activo
        if preview_activo is not None and preview_activo != envoltorio:
            try:
                preview_activo._cerrar_preview()
            except Exception:
                pass
        preview_activo = envoltorio
        if estado_hover["ocultar_id"] is not None:
            try:
                envoltorio.after_cancel(estado_hover["ocultar_id"])
            except Exception:
                pass
            estado_hover["ocultar_id"] = None
        if estado_hover["activo"]:
            return
        estado_hover["activo"] = True
        # Aplicar highlight al envoltorio externo
        envoltorio.configure(highlightbackground=paleta["base"], highlightthickness=2)
        if label_imagen is not None:
            animar(True)
        else:
            aplicar_colores(True)

    def ocultar_preview(event=None):
        """Oculta al salir; una entrada inmediata a un hijo cancela el cierre."""
        if estado_hover["ocultar_id"] is not None:
            try:
                envoltorio.after_cancel(estado_hover["ocultar_id"])
            except Exception:
                pass

        def comprobar_salida():
            estado_hover["ocultar_id"] = None
            ocultar_preview_ahora()

        estado_hover["ocultar_id"] = envoltorio.after(20, comprobar_salida)

    def ocultar_preview_ahora():
        global preview_activo
        if not estado_hover["activo"]:
            return
        estado_hover["activo"] = False
        # Aplicar highlight al envoltorio externo
        envoltorio.configure(highlightbackground=color_interfaz("#2a2a2a"), highlightthickness=1)
        if label_imagen is not None:
            animar(False)
        else:
            aplicar_colores(False)
        if preview_activo == envoltorio:
            preview_activo = None

    def cerrar_preview_inmediato():
        global preview_activo
        if estado_hover["ocultar_id"] is not None:
            try:
                envoltorio.after_cancel(estado_hover["ocultar_id"])
            except Exception:
                pass
            estado_hover["ocultar_id"] = None
        estado_hover["animacion"] += 1
        estado_hover["activo"] = False
        if label_imagen is not None and label_imagen.winfo_exists():
            label_imagen.place_forget()
        if label_texto is not None and label_texto.winfo_exists():
            label_texto.pack(anchor="w")
        if label_texto_extra is not None and label_texto_extra.winfo_exists():
            label_texto_extra.pack(anchor="w", pady=(2, 0))
        aplicar_colores(False)
        if preview_activo == envoltorio:
            preview_activo = None

    envoltorio._cerrar_preview = cerrar_preview_inmediato

    def abrir_articulo(event=None):
        if not link:
            return
        webbrowser.open(link)
        marcar_visto_y_redibujar(link)
        return "break"

    def enlazar_tarjeta(widget):
        """Las etiquetas también reciben eventos; las tratamos como parte de la tarjeta."""
        widget.bind("<Enter>", mostrar_preview, add="+")
        widget.bind("<Leave>", ocultar_preview, add="+")
        if link:
            widget.bind("<Button-1>", abrir_articulo, add="+")
        for hijo in widget.winfo_children():
            enlazar_tarjeta(hijo)

    enlazar_tarjeta(envoltorio)

    if label_imagen is not None:
        label_imagen.place_forget()


# La lectura queda deliberadamente sobria: el hover solo resalta el borde.
# Esta definición reemplaza el preview visual anterior, sin imágenes ni animaciones.
def preparar_preview_imagen(envoltorio, contenedor, label_texto, label_texto_extra, label_imagen, color_normal, color_hover, link=None, label_id=None):
    estado = {"monitor": False}

    def entrar(event=None):
        envoltorio.configure(highlightbackground=paleta["base"], highlightthickness=1)
        if not estado["monitor"]:
            estado["monitor"] = True
            vigilar_cursor()

    def cursor_sobre_tarjeta():
        try:
            x, y = envoltorio.winfo_pointerxy()
            widget = envoltorio.winfo_containing(x, y)
            while widget is not None:
                if widget == envoltorio:
                    return True
                widget = widget.master
        except Exception:
            pass
        return False

    def vigilar_cursor():
        if not cursor_sobre_tarjeta():
            estado["monitor"] = False
            try:
                envoltorio.configure(highlightbackground=color_interfaz("#2a2a2a"), highlightthickness=1)
            except Exception:
                pass
            return
        try:
            envoltorio.after(80, vigilar_cursor)
        except Exception:
            estado["monitor"] = False

    def abrir(event=None):
        if link:
            webbrowser.open(link)
            marcar_visto_y_redibujar(link)
            return "break"

    def enlazar(widget):
        # Solo activamos el monitor; no usamos <Leave> de hijos, que provoca
        # parpadeos al mover el cursor entre etiquetas internas.
        widget.bind("<Enter>", entrar, add="+")
        widget.bind("<Motion>", entrar, add="+")
        if link:
            widget.bind("<Button-1>", abrir, add="+")
        for hijo in widget.winfo_children():
            enlazar(hijo)

    enlazar(envoltorio)

# Renderer estable: registra la tarjeta para un único detector global de cursor.
def preparar_preview_imagen(envoltorio, contenedor, label_texto, label_texto_extra, label_imagen, color_normal, color_hover, link=None, label_id=None):
    def abrir(event=None):
        if link:
            webbrowser.open(link)
            marcar_visto_y_redibujar(link)
            return "break"

    def enlazar_click(widget):
        if link:
            widget.bind("<Button-1>", abrir, add="+")
        for hijo in widget.winfo_children():
            enlazar_click(hijo)

    envoltorio._es_tarjeta_articulo = True
    enlazar_click(envoltorio)


tarjeta_hover_actual = None


def actualizar_hover_tarjeta(event=None):
    """Resalta una sola tarjeta según la posición real del cursor."""
    global tarjeta_hover_actual
    try:
        widget = ventana.winfo_containing(event.x_root, event.y_root)
        tarjeta = None
        while widget is not None:
            if getattr(widget, "_es_tarjeta_articulo", False):
                tarjeta = widget
                break
            widget = widget.master
    except Exception:
        tarjeta = None

    if tarjeta == tarjeta_hover_actual:
        return

    if tarjeta_hover_actual is not None:
        try:
            tarjeta_hover_actual.configure(bg=color_interfaz("#2a2a2a"))
        except tk.TclError:
            pass

    tarjeta_hover_actual = tarjeta
    if tarjeta is not None:
        try:
            tarjeta.configure(bg=paleta["base"])
        except tk.TclError:
            tarjeta_hover_actual = None


def articulos_combinados_ver_todo():
    salida = []

    for categoria in config.get("categorias", []):
        for sitio_actual in categoria.get("sitios", []):
            url_sitio = sitio_actual.get("url")
            lista = datos_articulos.get(url_sitio) or []
            nombre_sitio = sitio_actual.get("nombre", "Fuente")

            for item in lista:
                if not item or not isinstance(item, (tuple, list)):
                    continue
                titulo = item[0] if len(item) > 0 else "(sin título)"
                link = item[1] if len(item) > 1 else ""
                titulo_es = item[2] if len(item) > 2 else ""
                imagen = item[3] if len(item) > 3 else None
                fecha = parsear_fecha_texto(item[4]) if len(item) > 4 else None
                salida.append({
                    "titulo": titulo,
                    "link": link,
                    "titulo_es": titulo_es,
                    "imagen": imagen,
                    "fecha": fecha,
                    "fuente": nombre_sitio,
                    "icono": obtener_imagen_favicon(sitio_actual),
                    "traducir_es": mostrar_titulo_traducido_sitio(sitio_actual),
                })

    salida.sort(
        key=lambda x: (
            x["fecha"].timestamp() if x["fecha"] is not None else float("-inf"),
            x["titulo"].lower(),
        ),
        reverse=True,
    )
    return salida


def articulos_combinados_categoria(nombre_categoria, url_fuente=None):
    categoria = next((c for c in config.get("categorias", []) if c.get("nombre") == nombre_categoria), None)
    if categoria is None:
        return []

    salida = []

    for sitio_actual in categoria.get("sitios", []):
        if url_fuente is not None and sitio_actual.get("url") != url_fuente:
            continue
        url_sitio = sitio_actual.get("url")
        lista = datos_articulos.get(url_sitio) or []
        nombre_sitio = sitio_actual.get("nombre", "Fuente")
        icono = obtener_imagen_favicon(sitio_actual)

        for item in lista:
            if not item or not isinstance(item, (tuple, list)):
                continue
            titulo = item[0] if len(item) > 0 else "(sin título)"
            link = item[1] if len(item) > 1 else ""
            titulo_es = item[2] if len(item) > 2 else ""
            imagen = item[3] if len(item) > 3 else None
            fecha = parsear_fecha_texto(item[4]) if len(item) > 4 else None
            salida.append({
                "titulo": titulo,
                "link": link,
                "titulo_es": titulo_es,
                "imagen": imagen,
                "fecha": fecha,
                "fuente": nombre_sitio,
                "icono": icono,
                "traducir_es": mostrar_titulo_traducido_sitio(sitio_actual),
            })

    salida.sort(
        key=lambda x: (
            x["fecha"].timestamp() if x["fecha"] is not None else float("-inf"),
            x["titulo"].lower(),
        ),
        reverse=True,
    )
    return salida


def ancho_usable_actual():
    try:
        return max(200, canvas.winfo_width())
    except Exception:
        return max(200, ancho_actual - ANCHO_MENU - 24)


def total_no_leidos_global():

    total = 0

    for categoria in config["categorias"]:

        for sitio_actual in categoria["sitios"]:
            total += contar_no_leidos(datos_articulos.get(sitio_actual["url"]))

    return total


def actualizar_color_mini():

    if mini_etiqueta is None:
        return

    total = total_no_leidos_global()

    mini_etiqueta.config(fg=color_interfaz("#8fbf7f") if total > 0 else color_interfaz("#666666"))


def minimizar():

    global minimizado, mini_ventana, mini_etiqueta

    if minimizado:
        return

    minimizado = True

    x_actual = ventana.winfo_x()
    y_actual = ventana.winfo_y()

    ventana.withdraw()

    mini_ventana = tk.Toplevel(ventana)

    mini_ventana.overrideredirect(True)

    mini_ventana.attributes("-topmost", True)

    mini_ventana.configure(bg=color_interfaz("#171717"))

    tamano = 34

    mini_ventana.geometry(f"{tamano}x{tamano}+{x_actual}+{y_actual}")

    marco_mini = tk.Frame(
        mini_ventana, bg=color_interfaz("#171717"),
        highlightbackground=color_interfaz("#454545"), highlightthickness=1
    )

    marco_mini.pack(fill="both", expand=True)

    mini_etiqueta = tk.Label(
        marco_mini, text="📰", font=("Sans", 14), bg=color_interfaz("#171717"), cursor="hand2"
    )

    mini_etiqueta.pack(fill="both", expand=True)

    for widget in (marco_mini, mini_etiqueta):
        widget.bind("<Button-1>", lambda event: restaurar())

    actualizar_color_mini()


def restaurar():

    global minimizado, mini_ventana, mini_etiqueta

    if mini_ventana is not None:

        try:
            mini_ventana.destroy()
        except Exception:
            pass

        mini_ventana = None
        mini_etiqueta = None

    minimizado = False

    ventana.deiconify()
    ventana.lift()
    ventana.attributes("-topmost", True)

    refrescar_vista()


# minimizar_btn.bind("<Button-1>", lambda event: minimizar())


# ============================================================
# VISTA: LECTURA
# ============================================================

def refrescar_vista():
    if lector_activo is not None and lector_activo.winfo_exists():
        return
    if minimizado:
        actualizar_color_mini()
    elif modo_admin:
        vista_admin()
    else:
        vista_lectura()

def refrescar_vista_con_carga(callback):
    """Muestra indicador de carga animado antes de ejecutar el callback"""
    limpiar_contenido()
    
    # Contenedor para el indicador de carga
    contenedor_carga = tk.Frame(contenido, bg=color_interfaz("#111315"))
    contenedor_carga.pack(fill="both", expand=True)
    
    # Texto de carga animado
    estado_carga = {"texto": "Cargando", "indice": 0}
    puntos = ["", ".", "..", "..."]
    
    etiqueta_carga = tk.Label(
        contenedor_carga, 
        text="Cargando", 
        font=("Sans", 10), 
        fg=paleta["base_fuerte"], 
        bg=color_interfaz("#111315")
    )
    etiqueta_carga.pack(anchor="center", pady=50)
    
    def animar_puntos():
        if not contenedor_carga.winfo_exists():
            return
        estado_carga["indice"] = (estado_carga["indice"] + 1) % 4
        texto = "Cargando" + puntos[estado_carga["indice"]]
        etiqueta_carga.config(text=texto)
        ventana.after(300, animar_puntos)
    
    # Iniciar animación
    animar_puntos()
    
    # Actualizar la UI inmediatamente
    ventana.update_idletasks()
    
    # Ejecutar el callback después de un pequeño delay
    def ejecutar_callback():
        if contenedor_carga.winfo_exists():
            contenedor_carga.destroy()
        callback()
    
    ventana.after(100, ejecutar_callback)


def marcar_visto_y_redibujar(link):

    if link:
        vistos.add(link)
        config["vistos"] = list(vistos)
        guardar_config()
        refrescar_vista()


def refrescar_vista_debounced():
    global ui_refresh_pending
    if ui_refresh_pending:
        return
    ui_refresh_pending = True
    ventana.after(80, lambda: (refrescar_vista(), set_ui_refresh_done()))


def set_ui_refresh_done():
    global ui_refresh_pending
    ui_refresh_pending = False


def alternar_categoria(nombre_cat):
    expandido_categoria[nombre_cat] = not expandido_categoria.get(nombre_cat, False)
    refrescar_vista_debounced()


def seleccionar_categoria(nombre_cat):
    global categoria_activa, vista_actual, filtro_principal
    if vista_actual == "categoria" and categoria_activa == nombre_cat:
        volver_a_categorias()
        return
    categoria_activa = nombre_cat
    vista_actual = "categoria"
    filtro_principal = nombre_cat
    refrescar_vista_con_carga(lambda: refrescar_vista())


def seleccionar_filtro(nombre_filtro):
    global categoria_activa, vista_actual, filtro_principal, fuente_activa
    fuente_activa = None
    if nombre_filtro == "todo":
        categoria_activa = None
        vista_actual = "categorias"
        filtro_principal = "todo"
    else:
        categoria_activa = nombre_filtro
        vista_actual = "categoria"
        filtro_principal = nombre_filtro
    refrescar_vista_con_carga(lambda: refrescar_vista())


def alternar_categoria_menu(nombre):
    if nombre in categorias_menu_expandidas:
        categorias_menu_expandidas.remove(nombre)
    else:
        categorias_menu_expandidas.add(nombre)
    refrescar_menu_lateral()


def navegar_menu(nombre=None, url=None):
    global modo_admin, categoria_activa, fuente_activa, vista_actual, filtro_principal
    modo_admin = False
    categoria_activa = nombre
    fuente_activa = url
    vista_actual = "fuente" if url else ("categoria" if nombre else "categorias")
    filtro_principal = nombre if nombre is not None else "todo"
    actualizar_estado_botones_inferiores()
    canvas.yview_moveto(0)
    vista_lectura()


def refrescar_menu_lateral():
    posicion = canvas_menu.yview()[0]
    for widget in contenido_menu.winfo_children():
        widget.destroy()

    def opcion(texto, comando, activa=False, sangria=0, indicador=None, cantidad=None):
        activa = activa and not modo_admin
        fondo = color_interfaz("#242a32") if activa else color_interfaz("#191d23")
        fila = tk.Frame(contenido_menu, bg=fondo, cursor="hand2", takefocus=True,
                        highlightthickness=1, highlightbackground=fondo,
                        highlightcolor=paleta["base"])
        fila.pack(fill="x", padx=(12 + sangria, 12), pady=2)
        marca = tk.Frame(fila, width=2, bg=paleta["base"] if activa else fondo)
        marca.pack(side="left", fill="y", pady=9)
        elementos = []
        if indicador:
            icono = tk.Label(fila, text=indicador, font=("Sans", 10),
                            fg=paleta["base_fuerte"] if activa else color_interfaz("#7f8997"), bg=fondo)
            icono.pack(side="left", padx=(9, 0))
            elementos.append(icono)
        if cantidad is not None:
            contador = tk.Label(fila, text=str(cantidad), font=("Sans", 8),
                               fg=color_interfaz("#8793a3"), bg=fondo)
            contador.pack(side="right", padx=(6, 10))
            elementos.append(contador)
        etiqueta = tk.Label(
            fila, text=texto, anchor="w", justify="left",
            font=("Sans", 9, "normal" if sangria else "bold"),
            fg=paleta["base_fuerte"] if activa else (color_interfaz("#aab4c1") if sangria else color_interfaz("#e0e6ee")),
            bg=fondo, pady=10 if not sangria else 8,
        )
        etiqueta.pack(side="left", fill="x", expand=True, padx=(10, 8))
        etiqueta.bind("<Configure>", lambda e: etiqueta.config(wraplength=max(40, e.width)))
        elementos.append(etiqueta)

        def resaltar(encima):
            color = color_interfaz("#2b323c") if encima else fondo
            fila.config(bg=color, highlightbackground=color)
            for elemento in elementos:
                elemento.config(bg=color)
            if not activa:
                marca.config(bg=color)

        def salir(event):
            x, y = fila.winfo_pointerxy()
            if not (fila.winfo_rootx() <= x < fila.winfo_rootx() + fila.winfo_width()
                    and fila.winfo_rooty() <= y < fila.winfo_rooty() + fila.winfo_height()):
                resaltar(False)

        for widget in (fila, marca, *elementos):
            widget.bind("<Enter>", lambda e: resaltar(True))
            widget.bind("<Leave>", salir)
            widget.bind("<Button-1>", lambda e: comando())
        fila.bind("<Return>", lambda e: comando())
        fila.bind("<space>", lambda e: comando())

    opcion("Todo el feed", navegar_menu, categoria_activa is None and vista_actual not in {"guardados", "descargas"}, indicador="≡")
    opcion("Guardados", lambda: abrir_biblioteca("guardados"), vista_actual == "guardados", indicador="◇")
    opcion("Descargas", lambda: abrir_biblioteca("descargas"), vista_actual == "descargas", indicador="↓")
    dibujar_switch_radar(contenido_menu)
    tk.Frame(contenido_menu, bg=color_interfaz("#2b313a"), height=1).pack(fill="x", padx=22, pady=(12, 16))
    tk.Label(contenido_menu, text="TUS CATEGORÍAS", font=("Sans", 7, "bold"),
             fg=color_interfaz("#788596"), bg=color_interfaz("#191d23")).pack(anchor="w", padx=24, pady=(0, 8))
    for categoria in config["categorias"]:
        nombre = categoria["nombre"]
        abierta = nombre in categorias_menu_expandidas
        opcion(nombre, lambda n=nombre: alternar_categoria_menu(n),
               categoria_activa == nombre, indicador="⌄" if abierta else "›",
               cantidad=len(categoria.get("sitios", [])))
        if abierta:
            opcion("Todas las fuentes", lambda n=nombre: navegar_menu(n),
                   categoria_activa == nombre and fuente_activa is None, 20)
            for fuente in categoria.get("sitios", []):
                url = fuente["url"]
                opcion(fuente["nombre"], lambda n=nombre, u=url: navegar_menu(n, u),
                       categoria_activa == nombre and fuente_activa == url, 20)
            if not categoria.get("sitios"):
                tk.Label(contenido_menu, text="Aún no hay fuentes", bg=color_interfaz("#191d23"),
                         fg=color_interfaz("#788596"), font=("Sans", 8)).pack(anchor="w", padx=44, pady=8)
            tk.Frame(contenido_menu, bg=color_interfaz("#191d23"), height=6).pack()
    contenido_menu.update_idletasks()
    canvas_menu.configure(scrollregion=canvas_menu.bbox("all"))
    canvas_menu.yview_moveto(posicion)


# Estado fijo al pie: permanece visible aunque se desplacen las categorías.
pie_menu = tk.Frame(menu_lateral, bg=color_interfaz("#191d23"))
pie_menu.pack(side="bottom", fill="x")
tk.Frame(pie_menu, bg=color_interfaz("#2b313a"), height=1).pack(fill="x", padx=22)
pie_estado = tk.Label(
    pie_menu, text="Cargando…", font=("Sans", 7),
    fg=color_interfaz("#8793a3"), bg=color_interfaz("#191d23"), anchor="w", justify="left",
    wraplength=ANCHO_MENU - 44,
)
pie_estado.pack(fill="x", padx=22, pady=14)

tk.Frame(menu_lateral, bg=color_interfaz("#2b313a"), height=1).pack(fill="x", padx=22, pady=(0, 12))
canvas_menu = tk.Canvas(menu_lateral, bg=color_interfaz("#191d23"), highlightthickness=0, width=290)
scroll_menu = tk.Scrollbar(
    menu_lateral, orient="vertical", command=canvas_menu.yview, width=6,
    bg=color_interfaz("#3b4552"), activebackground=color_interfaz("#576476"), troughcolor=color_interfaz("#191d23"),
    relief="flat", bd=0, highlightthickness=0,
)
canvas_menu.pack(side="left", fill="both", expand=True, pady=(0, 14))

def actualizar_scroll_menu(inicio, fin):
    scroll_menu.set(inicio, fin)
    if float(inicio) <= 0 and float(fin) >= 1:
        scroll_menu.pack_forget()
    elif not scroll_menu.winfo_manager():
        scroll_menu.pack(side="right", fill="y", before=canvas_menu, pady=(0, 14))

canvas_menu.configure(yscrollcommand=actualizar_scroll_menu)
contenido_menu = tk.Frame(canvas_menu, bg=color_interfaz("#191d23"))
contenido_menu_id = canvas_menu.create_window((0, 0), window=contenido_menu, anchor="nw")
canvas_menu.bind("<Configure>", lambda event: canvas_menu.itemconfigure(contenido_menu_id, width=event.width))
contenido_menu.bind("<Configure>", lambda event: canvas_menu.configure(scrollregion=canvas_menu.bbox("all")))


def volver_a_categorias():
    global categoria_activa, vista_actual, filtro_principal
    categoria_activa = None
    vista_actual = "categorias"
    filtro_principal = "todo"
    refrescar_vista_con_carga(lambda: refrescar_vista())


def alternar_sitio(url_sitio):

    expandido_sitio[url_sitio] = not expandido_sitio.get(url_sitio, False)
    refrescar_vista_debounced()


def vista_lectura_legacy():

    posicion_scroll = canvas.yview()[0]
    referencias_imagenes_articulos.clear()
    limpiar_contenido()

    barra_filtros = tk.Frame(contenido, bg=color_interfaz("#111315"))
    barra_filtros.pack(fill="x", pady=(0, 8))

    categorias_orden = ["todo"] + [c["nombre"] for c in config["categorias"]]
    contenedor_textos = tk.Frame(barra_filtros, bg=color_interfaz("#111315"))
    contenedor_textos.pack(anchor="center")

    for indice, nombre_filtro in enumerate(categorias_orden):
        etiqueta = "Ver todo" if nombre_filtro == "todo" else nombre_filtro
        activo = (filtro_principal == nombre_filtro)
        color = paleta["base_fuerte"] if activo else color_interfaz("#7c838b")

        if indice > 0:
            sep = tk.Label(contenedor_textos, text="|", fg=color_interfaz("#4b5158"), bg=color_interfaz("#111315"), font=("Sans", 8, "bold"))
            sep.pack(side="left", padx=(0, 8))

        item = tk.Label(
            contenedor_textos,
            text=etiqueta,
            fg=color,
            bg=color_interfaz("#111315"),
            font=("Sans", 8, "bold"),
            cursor="hand2"
        )
        item.pack(side="left")
        item.bind("<Button-1>", lambda event, n=nombre_filtro: seleccionar_filtro(n))
        item.bind("<Enter>", lambda event, w=item, c=paleta["base_fuerte"]: w.config(fg=c))
        item.bind("<Leave>", lambda event, w=item, c=(paleta["base_fuerte"] if activo else color_interfaz("#7c838b")): w.config(fg=c))

    if vista_actual == "categoria" and categoria_activa is not None:
        categoria = next((c for c in config["categorias"] if c["nombre"] == categoria_activa), None)

        if categoria is not None:
            cabecera_categoria = tk.Frame(contenido, bg=color_interfaz("#111315"))
            cabecera_categoria.pack(fill="x", pady=(0, 8))

            tk.Label(
                cabecera_categoria,
                text=categoria["nombre"],
                font=("Sans", 10, "bold"),
                fg=color_interfaz("#f2f2f2"),
                bg=color_interfaz("#111315"),
                justify="center"
            ).pack(anchor="center", padx=10, pady=(4, 4))

            tk.Frame(cabecera_categoria, bg=color_interfaz("#3a3d41"), height=1).pack(fill="x", padx=0, pady=(0, 0))

            articulos_categoria = articulos_combinados_categoria(categoria["nombre"])
            if not articulos_categoria:
                tk.Label(contenido, text="Sin artículos.", font=("Sans", 7), fg=color_interfaz("#888888"), bg=color_interfaz("#111315")).pack(anchor="center", pady=(12, 0))
            else:
                ancho_ventana = ancho_usable_actual()
                columnas = columnas_para_ancho(ancho_ventana)
                estilo = estilo_tarjeta_por_columnas(columnas)
                contenedor_articulos = tk.Frame(contenido, bg=color_interfaz("#111315"))
                contenedor_articulos.pack(fill="x", pady=(0, 10))

                for idx in range(0, len(articulos_categoria), columnas):
                    for col in range(columnas):
                        contenedor_articulos.grid_columnconfigure(col, weight=1)

                for idx, articulo in enumerate(articulos_categoria):
                    titulo = articulo["titulo"]
                    link = articulo["link"]
                    titulo_es = articulo["titulo_es"]
                    imagen_bytes = articulo["imagen"]
                    fuente = articulo["fuente"]
                    icono = articulo["icono"]
                    ya_visto = link in vistos
                    color_normal = color_interfaz("#666666") if ya_visto else paleta["link"]
                    color_hover = color_interfaz("#888888") if ya_visto else paleta["link_hover"]
                    ancho_wrap = max(180, int((ancho_ventana - 90) / columnas)) if columnas > 1 else ancho_ventana - 80

                    ancho_tarjeta = max(180, int((ancho_ventana - 90) / columnas)) if columnas > 1 else ancho_ventana - 60
                    alto_tarjeta = estilo["alto"]

                    envoltorio = tk.Frame(
                        contenedor_articulos,
                        # Borde real fijo de 1 px: evitamos el highlight
                        # nativo de Tk, que repinta la grilla al cambiar de tarjeta.
                        bg=color_interfaz("#2a2a2a"),
                        width=ancho_tarjeta,
                        height=alto_tarjeta
                    )
                    envoltorio.grid(row=idx // columnas, column=idx % columnas, sticky="nsew", padx=4, pady=4)
                    envoltorio.grid_propagate(False)

                    superficie_tarjeta = tk.Frame(envoltorio, bg=color_interfaz("#171717"))
                    superficie_tarjeta.pack(fill="both", expand=True, padx=1, pady=1)
                    contenido_tarjeta = tk.Frame(superficie_tarjeta, bg=color_interfaz("#171717"))
                    contenido_tarjeta.pack(fill="both", expand=True, padx=7, pady=7)

                    fila_fuente = tk.Frame(contenido_tarjeta, bg=color_interfaz("#171717"))
                    fila_fuente.pack(anchor="w", pady=(0, 4))
                    if icono is not None:
                        tk.Label(fila_fuente, image=icono, bg=color_interfaz("#171717")).pack(side="left")
                    tk.Label(
                        fila_fuente,
                        text=f"{fuente}",
                        font=("Sans", estilo["fuente"], "bold"),
                        fg=paleta["base_fuerte"],
                        bg=color_interfaz("#171717")
                    ).pack(side="left", padx=(6, 0) if icono is not None else (0, 0))
                    
                    columna_texto = tk.Frame(contenido_tarjeta, bg=color_interfaz("#171717"))
                    columna_texto.pack(fill="x", expand=True)

                    etiqueta_articulo = tk.Label(
                        columna_texto,
                        text="•  " + titulo,
                        font=("Sans", estilo["titulo"]),
                        fg=color_normal,
                        bg=color_interfaz("#171717"),
                        justify="left",
                        wraplength=max(180, ancho_wrap - 30),
                        cursor="hand2"
                    )
                    etiqueta_articulo.pack(anchor="w")

                    etiqueta_traducida = None
                    if titulo_es and articulo.get("traducir_es", False):
                        etiqueta_traducida = tk.Label(
                            columna_texto,
                            text="   " + titulo_es,
                            font=("Sans", estilo["traducido"]),
                            fg=color_interfaz("#aaaaaa") if not ya_visto else color_interfaz("#666666"),
                            bg=color_interfaz("#171717"),
                            justify="left",
                            wraplength=max(180, ancho_wrap - 30)
                        )
                        etiqueta_traducida.pack(anchor="w", pady=(2, 0))

                    etiqueta_imagen = None
                    
                    preparar_preview_imagen(envoltorio, envoltorio, etiqueta_articulo, etiqueta_traducida, etiqueta_imagen, color_normal, color_hover, link=link, label_id="card")

                    contenido_tarjeta.configure(cursor="hand2")

    elif filtro_principal == "todo":
        articulos_totales = articulos_combinados_ver_todo()
        if not articulos_totales:
            tk.Label(contenido, text="Sin artículos.", font=("Sans", 7), fg=color_interfaz("#888888"), bg=color_interfaz("#111315")).pack(anchor="center", pady=(12, 0))
        else:
            ancho_ventana = ancho_usable_actual()
            columnas = columnas_para_ancho(ancho_ventana)
            estilo = estilo_tarjeta_por_columnas(columnas)
            contenedor_articulos = tk.Frame(contenido, bg=color_interfaz("#111315"))
            contenedor_articulos.pack(fill="x", pady=(0, 10))

            for col in range(columnas):
                contenedor_articulos.grid_columnconfigure(col, weight=1)

            for idx, articulo in enumerate(articulos_totales):
                titulo = articulo["titulo"]
                link = articulo["link"]
                titulo_es = articulo["titulo_es"]
                imagen_bytes = articulo["imagen"]
                fuente = articulo["fuente"]
                icono = articulo["icono"]
                ya_visto = link in vistos
                color_normal = color_interfaz("#666666") if ya_visto else paleta["link"]
                color_hover = color_interfaz("#888888") if ya_visto else paleta["link_hover"]
                ancho_wrap = max(180, int((ancho_ventana - 90) / columnas)) if columnas > 1 else ancho_ventana - 80

                ancho_tarjeta = max(180, int((ancho_ventana - 90) / columnas)) if columnas > 1 else ancho_ventana - 60
                alto_tarjeta = estilo["alto"]

                envoltorio = tk.Frame(
                    contenedor_articulos,
                    # Borde real fijo de 1 px; el hover solo cambia este color.
                    bg=color_interfaz("#2a2a2a"),
                    width=ancho_tarjeta,
                    height=alto_tarjeta
                )
                envoltorio.grid(row=idx // columnas, column=idx % columnas, sticky="nsew", padx=4, pady=4)
                envoltorio.grid_propagate(False)

                superficie_tarjeta = tk.Frame(envoltorio, bg=color_interfaz("#171717"))
                superficie_tarjeta.pack(fill="both", expand=True, padx=1, pady=1)
                contenido_tarjeta = tk.Frame(superficie_tarjeta, bg=color_interfaz("#171717"))
                contenido_tarjeta.pack(fill="both", expand=True, padx=7, pady=7)

                fila_fuente = tk.Frame(contenido_tarjeta, bg=color_interfaz("#171717"))
                fila_fuente.pack(anchor="w", pady=(0, 4))
                if icono is not None:
                    tk.Label(fila_fuente, image=icono, bg=color_interfaz("#171717")).pack(side="left")
                tk.Label(
                    fila_fuente,
                    text=fuente,
                    font=("Sans", estilo["fuente"], "bold"),
                    fg=paleta["base_fuerte"],
                    bg=color_interfaz("#171717")
                ).pack(side="left", padx=(6, 0) if icono is not None else (0, 0))
                
                columna_texto = tk.Frame(contenido_tarjeta, bg=color_interfaz("#171717"))
                columna_texto.pack(fill="x", expand=True)

                etiqueta_articulo = tk.Label(
                    columna_texto,
                    text="•  " + titulo,
                    font=("Sans", estilo["titulo"]),
                    fg=color_normal,
                    bg=color_interfaz("#171717"),
                    justify="left",
                    wraplength=max(180, ancho_wrap - 30),
                    cursor="hand2"
                )
                etiqueta_articulo.pack(anchor="w")

                etiqueta_traducida = None
                if titulo_es and articulo.get("traducir_es", False):
                    etiqueta_traducida = tk.Label(
                        columna_texto,
                        text="   " + titulo_es,
                        font=("Sans", estilo["traducido"]),
                        fg=color_interfaz("#aaaaaa") if not ya_visto else color_interfaz("#666666"),
                        bg=color_interfaz("#171717"),
                        justify="left",
                        wraplength=max(180, ancho_wrap - 30)
                    )
                    etiqueta_traducida.pack(anchor="w", pady=(2, 0))

                etiqueta_imagen = None
                
                preparar_preview_imagen(envoltorio, envoltorio, etiqueta_articulo, etiqueta_traducida, etiqueta_imagen, color_normal, color_hover, link=link, label_id="card")

                contenido_tarjeta.configure(cursor="hand2")

    else:
        for categoria in config["categorias"]:
            nombre_cat = categoria["nombre"]
            total_no_leidos = sum(contar_no_leidos(datos_articulos.get(s["url"])) for s in categoria["sitios"])

            fila_categoria = tk.Frame(contenido, bg=color_interfaz("#111315"), cursor="hand2")
            fila_categoria.pack(fill="x")
            fila_categoria.bind("<Button-1>", lambda event, n=nombre_cat: seleccionar_categoria(n))

            linea = tk.Frame(contenido, bg=color_interfaz("#2a2d31"), height=1)
            linea.pack(fill="x", pady=(0, 0))

            contenido_fila = tk.Frame(fila_categoria, bg=color_interfaz("#111315"), padx=0, pady=10)
            contenido_fila.pack(fill="x")

            titulo_card = tk.Label(
                contenido_fila,
                text=nombre_cat,
                font=("Sans", 9, "bold"),
                fg=color_interfaz("#dfe3e7"),
                bg=color_interfaz("#111315"),
                cursor="hand2",
                justify="center",
                anchor="center"
            )
            titulo_card.pack(anchor="center")
            titulo_card.bind("<Button-1>", lambda event, n=nombre_cat: seleccionar_categoria(n))

            detalle = tk.Label(
                contenido_fila,
                text=f"{len(categoria['sitios'])} fuentes" + (f" · {total_no_leidos} nuevos" if total_no_leidos > 0 else ""),
                font=("Sans", 7),
                fg=color_interfaz("#8b9198"),
                bg=color_interfaz("#111315"),
                justify="center",
                cursor="hand2",
                anchor="center"
            )
            detalle.pack(anchor="center", pady=(4, 0))
            detalle.bind("<Button-1>", lambda event, n=nombre_cat: seleccionar_categoria(n))

            def on_enter_label(event, label=titulo_card):
                label.configure(fg=paleta["base_fuerte"])

            def on_leave_label(event, label=titulo_card):
                label.configure(fg=color_interfaz("#dfe3e7"))

            titulo_card.bind("<Enter>", on_enter_label)
            titulo_card.bind("<Leave>", on_leave_label)
            detalle.bind("<Enter>", lambda event: detalle.configure(fg=paleta["base_fuerte"]))
            detalle.bind("<Leave>", lambda event: detalle.configure(fg=color_interfaz("#8b9198")))
            fila_categoria.bind("<Enter>", lambda event: (titulo_card.configure(fg=paleta["base_fuerte"]), detalle.configure(fg=paleta["base_fuerte"])))
            fila_categoria.bind("<Leave>", lambda event: (titulo_card.configure(fg=color_interfaz("#dfe3e7")), detalle.configure(fg=color_interfaz("#8b9198"))))

    pie_estado.config(
        text="Última actualización: " + datetime.now().strftime("%H:%M")
    )

    ajustar_alto_auto()
    canvas.yview_moveto(posicion_scroll)


# ============================================================
# TARJETAS DE ARTÍCULOS — IMPLEMENTACIÓN LIMPIA
# ============================================================

tarjeta_hover_actual = None
lector_activo = None
actualizacion_en_curso = False


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


def carpeta_descargas():
    """Respeta la carpeta XDG del usuario, incluso si está en otro disco."""
    try:
        resultado = subprocess.run(["xdg-user-dir", "DOWNLOAD"], capture_output=True,
                                   text=True, timeout=2, check=True)
        ruta = resultado.stdout.strip()
        if os.path.isabs(ruta) and os.path.isdir(ruta):
            return ruta
    except (OSError, subprocess.SubprocessError):
        pass
    for nombre in ("Descargas", "Downloads"):
        ruta = os.path.expanduser("~/" + nombre)
        if os.path.isdir(ruta):
            return ruta
    return os.path.expanduser("~")


def previsualizar_cita(fragmento, articulo, link, traducida=False):
    if not PIL_DISPONIBLE:
        messagebox.showerror("Imagen", "Se necesita Pillow para generar la imagen.")
        return
    dialogo = tk.Toplevel(ventana)
    dialogo.title("Preparar imagen de la cita")
    dialogo.configure(bg="#e1e1e1")
    ancho = min(820, dialogo.winfo_screenwidth() - 60)
    alto = min(580, dialogo.winfo_screenheight() - 100)
    dialogo.geometry(f"{ancho}x{alto}")
    acciones = tk.Frame(dialogo, bg="#e1e1e1")
    acciones.pack(side="bottom", fill="x", padx=16, pady=12)
    panel = tk.Frame(dialogo, bg="#e1e1e1")
    panel.pack(fill="both", expand=True)
    opciones = tk.Frame(panel, bg="#e1e1e1")
    opciones.pack(side="left", fill="y", padx=16, pady=12)
    version = tk.StringVar(value="Español" if traducida else "Original")
    incluir_imagen = tk.BooleanVar(value=False)
    color = tk.StringVar(value=config.get("color", "gris"))
    idioma = tk.StringVar(value=articulo.get("idioma_original", ""))
    def rotulo(texto):
        tk.Label(opciones, text=texto, bg="#e1e1e1", fg="#252525").pack(anchor="w", pady=(8, 4))
    def alternar_version():
        if traducida:
            messagebox.showinfo("Original exacto", "Vuelve al artículo original y selecciona allí el fragmento para conservar sus palabras exactas.", parent=dialogo)
            return
        version.set("Original" if version.get() == "Español" else "Español")
        boton_version.config(text="Mostrar idioma original" if version.get() == "Español" else "Mostrar traducción")
    boton_version = tk.Button(opciones, text="Mostrar idioma original" if traducida else "Mostrar traducción",
        command=alternar_version, bg="#cccccc", fg="#252525", relief="flat", bd=0, padx=12, pady=8)
    boton_version.pack(anchor="w", pady=6)
    tk.Checkbutton(opciones, text="Incluir imagen del artículo", variable=incluir_imagen,
                   state="normal" if articulo.get("imagen") else "disabled",
                   indicatoron=False, relief="flat", bd=0, padx=12, pady=8, cursor="hand2",
                   bg="#e1e1e1", fg="#252525", selectcolor="#cccccc",
                   activebackground="#e1e1e1", activeforeground="#171717").pack(anchor="w", pady=8)
    def actualizar_color():
        nombre = color.get()
        boton_color.config(text="Color " + NOMBRES_TEMAS[nombre],
            fg=PALETA_TEMAS[nombre]["base_fuerte"],
            bg="#e6e6e6" if nombre == "periodico" else "#232a34")
    def siguiente_color():
        nombres = list(NOMBRES_TEMAS)
        color.set(nombres[(nombres.index(color.get()) + 1) % len(nombres)])
        actualizar_color()
    boton_color = tk.Button(opciones, command=siguiente_color, relief="flat", bd=0,
                            padx=12, pady=8, cursor="hand2", font=("Sans", 9))
    boton_color.pack(anchor="w", pady=8)
    actualizar_color()
    estado_preview = tk.Label(opciones, text="", wraplength=220,
                             bg="#e1e1e1", fg="#252525")
    estado_preview.pack(anchor="w", pady=8)
    espacio_preview = tk.Frame(panel, bg="#e1e1e1")
    espacio_preview.pack(side="left", fill="both", expand=True, padx=12, pady=12)
    etiqueta = tk.Label(espacio_preview, bg="#e1e1e1")
    etiqueta.place(relx=.5, rely=.5, anchor="center")
    imagen_actual = {"imagen": None}
    cache_es = {"texto": fragmento if traducida else None}
    pendiente = {"id": None, "traduciendo": False}
    def redimensionar(event=None):
        imagen = imagen_actual["imagen"]
        if imagen is None:
            return
        vista = imagen.copy()
        lado = max(40, min(espacio_preview.winfo_width(), espacio_preview.winfo_height()) - 8)
        vista.thumbnail((lado, lado))
        foto = foto_tk(vista)
        etiqueta.config(image=foto)
        etiqueta.image = foto
    espacio_preview.bind("<Configure>", redimensionar)
    def invalidar(*args):
        guardar_btn.config(state="disabled")
        if pendiente["id"] is not None:
            dialogo.after_cancel(pendiente["id"])
        pendiente["id"] = dialogo.after(100, generar)
    for variable in (version, incluir_imagen, color, idioma):
        variable.trace_add("write", invalidar)

    def generar():
        if not dialogo.winfo_exists():
            return
        opciones_actuales = (version.get(), incluir_imagen.get(), color.get(), idioma.get())
        pendiente["id"] = None
        estado_preview.config(text="Actualizando vista previa…")
        guardar_btn.config(state="disabled")
        def terminar(texto_cita):
            if not dialogo.winfo_exists():
                return
            estado_preview.config(text="")
            if texto_cita is None:
                messagebox.showerror("Traducción", "No se pudo traducir la cita. Puedes reintentar.", parent=dialogo)
                return
            if opciones_actuales != (version.get(), incluir_imagen.get(), color.get(), idioma.get()):
                return
            try:
                imagen = crear_imagen_cita(texto_cita, articulo.get("fuente", "Fuente"), link,
                    version.get() == "Español", titulo=articulo.get("titulo", ""), color=PALETA_TEMAS[color.get()]["base_fuerte"], tema=color.get(),
                    imagen_bytes=articulo.get("imagen") if incluir_imagen.get() else None,
                    idioma_original=idioma.get())
            except Exception as error:
                messagebox.showerror("Imagen", str(error), parent=dialogo)
                return
            imagen_actual["imagen"] = imagen
            redimensionar()
            guardar_btn.config(state="normal")
        if version.get() == "Español" and cache_es["texto"] is None:
            if pendiente["traduciendo"]:
                return
            pendiente["traduciendo"] = True
            def traduccion_lista(resultado):
                if not dialogo.winfo_exists():
                    return
                pendiente["traduciendo"] = False
                cache_es["texto"] = resultado
                if resultado is None:
                    estado_preview.config(text="No se pudo traducir. Cambia de idioma para reintentar.")
                else:
                    generar()
            def traducir_cita():
                resultado = traducir_texto(fragmento, "es")
                ventana.after(0, lambda: traduccion_lista(resultado))
            threading.Thread(target=traducir_cita, daemon=True).start()
        else:
            terminar(cache_es["texto"] if version.get() == "Español" else fragmento)

    def guardar():
        ruta = filedialog.asksaveasfilename(parent=dialogo, defaultextension=".png",
            initialdir=carpeta_descargas(), initialfile="cita.png", filetypes=[("Imagen PNG", "*.png"), ("Imagen JPG", "*.jpg *.jpeg")])
        if not ruta:
            return
        try:
            from PIL.PngImagePlugin import PngInfo
            metadata = PngInfo()
            metadata.add_text("Fuente", link)
            if os.path.splitext(ruta)[1].lower() in {".jpg", ".jpeg"}:
                imagen_actual["imagen"].convert("RGB").save(ruta, format="JPEG", quality=95, subsampling=0)
            else:
                imagen_actual["imagen"].save(ruta, format="PNG", pnginfo=metadata)
        except Exception as error:
            messagebox.showerror("No se pudo guardar", str(error), parent=dialogo)
            return
        dialogo.destroy()
    guardar_btn = tk.Button(acciones, text="Guardar imagen…", command=guardar, state="disabled",
        bg="#303640", fg="#f1f1f1", activebackground="#444e5b", activeforeground="#ffffff",
        disabledforeground="#8d939b", relief="flat", bd=0, padx=18, pady=10, cursor="hand2")
    guardar_btn.pack(side="left", padx=8)
    tk.Button(acciones, text="Cancelar", command=dialogo.destroy, bg="#cccccc", fg="#252525",
        activebackground="#bbbbbb", relief="flat", bd=0, padx=18, pady=10, cursor="hand2").pack(side="left", padx=8)

    dialogo.after_idle(generar)

def contenido_para_articulo(articulo):
    link = articulo["link"]
    if articulo.get("cuerpo"):
        return articulo["cuerpo"], articulo.get("estado_contenido", "Contenido guardado")
    if link in textos_articulos:
        return textos_articulos[link]
    local = biblioteca.leer("descargas", link)
    if local:
        return local["cuerpo"], local.get("estado_contenido", "Disponible sin conexión")
    cuerpo = ""
    try:
        html = descargar(link, timeout=15).decode("utf-8", errors="replace")
        idioma = re.search(r'<html\b[^>]*\blang=["\']([a-zA-Z]+)', html, re.IGNORECASE)
        if idioma:
            articulo["idioma_original"] = idioma.group(1).lower()
        cuerpo = texto_articulo(html)
    except Exception:
        pass
    estado = "Texto extraído del sitio"
    if not cuerpo:
        parser = ContenidoHTML()
        parser.feed(contenido_feed.get(link, ""))
        cuerpo = parser.texto()
        estado = "Contenido del feed · Puede ser un resumen"
    if cuerpo:
        textos_articulos[link] = (cuerpo, estado)
    return cuerpo, estado


def alternar_guardado(articulo, boton=None):
    link = articulo["link"]
    try:
        if biblioteca.contiene("guardados", link):
            biblioteca.borrar("guardados", link)
        else:
            biblioteca.guardar("guardados", articulo)
    except (OSError, ValueError) as error:
        messagebox.showerror("Guardados", str(error))
        return
    if boton is not None and boton.winfo_exists():
        boton.config(text="Quitar guardado" if biblioteca.contiene("guardados", link) else "Guardar")
    if boton is not None and getattr(boton, "_tipo_archivo", None):
        actualizar_icono_archivo(boton, articulo, "guardados")
    if vista_actual == "guardados" and not (lector_activo and lector_activo.winfo_exists()):
        vista_lectura()


def alternar_descarga(articulo, boton=None):
    link = articulo["link"]
    if link in descargas_en_curso:
        return
    if biblioteca.contiene("descargas", link):
        try:
            biblioteca.borrar("descargas", link)
        except OSError as error:
            messagebox.showerror("Descargas", str(error))
            return
        if boton is not None and boton.winfo_exists():
            boton.config(text="Descargar")
            if getattr(boton, "_tipo_archivo", None):
                actualizar_icono_archivo(boton, articulo, "descargas")
        if vista_actual == "descargas" and not (lector_activo and lector_activo.winfo_exists()):
            vista_lectura()
        return
    descargas_en_curso.add(link)
    if boton is not None:
        boton.config(text="Descargando…", state="disabled")
    def trabajo():
        error = None
        try:
            copia = dict(articulo)
            copia["cuerpo"], copia["estado_contenido"] = contenido_para_articulo(copia)
            if not copia.get("imagen"):
                url_imagen = obtener_imagen_og(link)
                if url_imagen:
                    try:
                        copia["imagen"] = descargar(url_imagen, timeout=8)
                    except Exception:
                        pass
            biblioteca.guardar("descargas", copia)
        except Exception as exc:
            error = str(exc)
        def terminar():
            descargas_en_curso.discard(link)
            if boton is not None and boton.winfo_exists():
                boton.config(text="Descargar" if error else "Eliminar descarga", state="normal")
                if getattr(boton, "_tipo_archivo", None):
                    actualizar_icono_archivo(boton, articulo, "descargas")
            if error:
                messagebox.showerror("Descargas", error)
            else:
                pie_estado.config(text="Artículo disponible sin conexión")
                if vista_actual == "descargas":
                    refrescar_vista()
        ventana.after(0, terminar)
    threading.Thread(target=trabajo, daemon=True).start()


def abrir_biblioteca(tipo):
    global vista_actual, modo_admin, lector_activo
    lector_activo = None
    modo_admin = False
    vista_actual = tipo
    actualizar_estado_botones_inferiores()
    vista_lectura()


def puntuacion_articulo(articulo):
    cuerpo = articulo.get("cuerpo") or textos_articulos.get(articulo["link"], ("", ""))[0]
    if not cuerpo:
        parser = ContenidoHTML()
        parser.feed(contenido_feed.get(articulo["link"], ""))
        cuerpo = parser.texto()
    return puntuar_radar(articulo.get("titulo", "") + " " + (articulo.get("titulo_es") or ""),
                         cuerpo, config.get("radar_palabras", []))


def analizar_radar():
    global radar_en_curso
    if radar_en_curso or not config.get("radar_activo") or not config.get("radar_palabras"):
        return
    radar_en_curso = True
    articulos = {a["link"]: a for a in articulos_combinados_ver_todo()}
    pie_estado.config(text="Radar: analizando contenido…")
    def trabajo():
        try:
            with ThreadPoolExecutor(max_workers=4) as ejecutor:
                list(ejecutor.map(contenido_para_articulo, articulos.values()))
        finally:
            def terminar():
                global radar_en_curso
                radar_en_curso = False
                refrescar_vista()
                pie_estado.config(text="Radar listo · Ordenado por intereses")
            ventana.after(0, terminar)
    threading.Thread(target=trabajo, daemon=True).start()


def alternar_radar():
    config["radar_activo"] = not config.get("radar_activo", False)
    guardar_config()
    refrescar_menu_lateral()
    refrescar_vista()
    if config["radar_activo"]:
        analizar_radar()


def crear_buscador(padre, variable, guia, ancho=200):
    fondo = color_interfaz("#111315")
    relleno = color_interfaz("#29313d")
    marco = tk.Canvas(padre, width=ancho, height=38, bg=fondo, highlightthickness=0, bd=0)
    entrada = tk.Entry(marco, textvariable=variable, relief="flat", bd=0, font=("Sans", 9),
                       bg=relleno, fg=paleta["texto"], insertbackground=paleta["texto"])
    entrada_id = marco.create_window(16, 19, window=entrada, anchor="w", width=ancho - 32)
    pista = tk.Label(marco, text=guia, bg=relleno, fg=paleta["texto_sec"], font=("Sans", 9), cursor="xterm")
    def actualizar_pista(*args):
        if not marco.winfo_exists():
            return
        if not variable.get() and entrada.focus_get() is not entrada:
            pista.place(x=16, y=8)
        else:
            pista.place_forget()
    def dibujar(event):
        nonlocal relleno
        relleno = color_interfaz("#29313d")
        marco.configure(bg=color_interfaz("#111315"))
        entrada.configure(bg=relleno, fg=paleta["texto"], insertbackground=paleta["texto"])
        pista.configure(bg=relleno, fg=paleta["texto_sec"])
        w = marco.winfo_width()
        marco.delete("fondo")
        marco.create_polygon(18, 1, w-18, 1, w-1, 1, w-1, 19, w-1, 37,
                             w-18, 37, 18, 37, 1, 37, 1, 19, 1, 1,
                             smooth=True, splinesteps=24, fill=relleno, outline=paleta["card_borde"], tags="fondo")
        marco.tag_lower("fondo")
        marco.itemconfigure(entrada_id, width=max(40, w-32))
    marco.bind("<Configure>", dibujar)
    pista.bind("<Button-1>", lambda e: entrada.focus_set())
    entrada.bind("<FocusIn>", actualizar_pista)
    entrada.bind("<FocusOut>", actualizar_pista)
    variable.trace_add("write", actualizar_pista)
    actualizar_pista()
    return marco, entrada


def icono_archivo(tipo, activo=False):
    if not PIL_DISPONIBLE:
        return None
    escala = 3
    imagen = Image.new("RGBA", (60, 60))
    dibujo = ImageDraw.Draw(imagen)
    color = paleta["base_fuerte"]
    if tipo == "guardados":
        dibujo.polygon([(15,9),(45,9),(45,51),(30,39),(15,51)],
                       fill=color if activo else None, outline=color, width=4)
    else:
        dibujo.line([(30,8),(30,36)], fill=color, width=5)
        dibujo.line([(18,25),(30,37),(42,25)], fill=color, width=5)
        dibujo.line([(12,39),(12,49),(48,49),(48,39)], fill=color, width=4)
        if activo:
            dibujo.ellipse((42,2,58,18), fill=color)
    return foto_tk(imagen.resize((20,20), Image.Resampling.LANCZOS))


def actualizar_icono_archivo(boton, articulo, tipo):
    foto = icono_archivo(tipo, biblioteca.contiene(tipo, articulo["link"]))
    if foto:
        boton.config(image=foto, compound="none", text="")
        boton.image = foto


def dibujar_switch_radar(padre):
    fila = tk.Frame(padre, bg=color_interfaz("#191d23"))
    fila.pack(fill="x", padx=22, pady=(6, 10))
    tk.Label(fila, text="Radar de intereses", font=("Sans", 9), bg=color_interfaz("#191d23"),
             fg=paleta["texto"]).pack(side="left")
    switch = tk.Canvas(fila, width=44, height=24, highlightthickness=0,
                       bg=color_interfaz("#191d23"), cursor="hand2", takefocus=True)
    switch.pack(side="right")
    activo = config.get("radar_activo", False)
    color = paleta["base"] if activo else "#858585"
    switch.create_line(12,12,32,12, fill=color, width=22, capstyle="round")
    x = 32 if activo else 12
    switch.create_oval(x-8,4,x+8,20, fill="#eeeeee", outline="")
    switch.bind("<Button-1>", lambda e: alternar_radar())
    switch.bind("<space>", lambda e: alternar_radar())


def ir_a_radar():
    global modo_admin, seccion_config, lector_activo
    lector_activo = None
    modo_admin = True
    seccion_config = "radar"
    vista_admin()


def _abrir_articulo(link, articulo=None):
    if not link:
        return
    global lector_activo
    articulo = articulo or {}
    panel_busqueda.pack_forget()
    lectura_sin_conexion = vista_actual == "descargas"
    posicion_anterior = canvas.yview()[0]
    limpiar_contenido()
    lector = tk.Frame(contenido, bg=color_interfaz("#171b20"))
    lector.pack(fill="both", expand=True)
    lector_activo = lector

    def volver():
        global lector_activo
        lector_activo = None
        vista_lectura()
        canvas.yview_moveto(posicion_anterior)

    cabecera_lector = tk.Frame(lector, bg=color_interfaz("#171b20"))
    cabecera_lector.pack(fill="x", padx=16, pady=16)
    def boton_lectura(padre, etiqueta, comando, destacado=False):
        fondo = color_interfaz("#29313d") if destacado else color_interfaz("#171b20")
        boton = tk.Button(
            padre, text=etiqueta, command=comando, font=("Sans", 8, "bold"),
            bg=fondo, fg=paleta["base_fuerte"] if destacado else color_interfaz("#aab4c1"),
            activebackground=color_interfaz("#354052"), activeforeground=color_interfaz("#edf1f7"),
            disabledforeground=color_interfaz("#667180"), relief="flat", bd=0,
            highlightthickness=0, padx=10, pady=8, cursor="hand2",
        )
        boton.bind("<Enter>", lambda e: boton.config(bg=color_interfaz("#354052")) if boton["state"] != "disabled" else None)
        boton.bind("<Leave>", lambda e: boton.config(bg=fondo))
        return boton

    boton_lectura(cabecera_lector, "← Volver al feed", volver).pack(anchor="w", pady=(0, 8))
    acciones_lectura = tk.Frame(cabecera_lector, bg=color_interfaz("#171b20"))
    acciones_lectura.pack(fill="x")
    boton_lectura(acciones_lectura, "Abrir original ↗", lambda: webbrowser.open(link)).pack(side="right")
    contenedor_portada = tk.Frame(lector, bg=color_interfaz("#171b20"))
    contenedor_portada.pack(fill="x", padx=20, pady=(0, 16))
    def mostrar_portada():
        if not config.get("mostrar_imagenes_lectura", True) or not articulo.get("imagen"):
            return
        if contenedor_portada.winfo_children():
            return
        ancho_portada = max(180, ancho_usable_actual() - 40)
        portada = cargar_miniatura_cubierta(articulo["imagen"], ancho_portada, min(280, ancho_portada * 9 // 16))
        if portada:
            imagen_lector = tk.Label(contenedor_portada, image=portada, bg=color_interfaz("#171b20"))
            imagen_lector.image = portada
            imagen_lector.pack(fill="x")
    mostrar_portada()
    acciones_archivo = tk.Frame(lector, bg=color_interfaz("#171b20"))
    acciones_archivo.pack(fill="x", padx=20, pady=(0, 10))
    guardar_articulo_btn = boton_lectura(acciones_archivo,
        "Quitar guardado" if biblioteca.contiene("guardados", link) else "Guardar",
        lambda: alternar_guardado(articulo, guardar_articulo_btn))
    guardar_articulo_btn.pack(side="left")
    descargar_articulo_btn = boton_lectura(acciones_archivo,
        "Eliminar descarga" if biblioteca.contiene("descargas", link) else "Descargar",
        lambda: alternar_descarga(articulo, descargar_articulo_btn))
    descargar_articulo_btn.pack(side="left")
    titulo = tk.Label(lector, text=articulo.get("titulo", "Artículo"),
                      font=("Sans", 16, "bold"), fg=color_interfaz("#edf1f7"), bg=color_interfaz("#171b20"),
                      justify="left", anchor="w")
    titulo.pack(fill="x", padx=20, pady=(0, 16))
    estado_label = tk.Label(lector, text="Cargando artículo…", font=("Sans", 9),
                           fg=color_interfaz("#8793a3"), bg=color_interfaz("#171b20"), justify="left", anchor="w")
    estado_label.pack(fill="x", padx=20, pady=(0, 16))
    lectura = {"original": "", "es": None, "traducida": False, "ocupada": False, "estado": ""}
    texto = tk.Text(lector, font=("Sans", 11), fg=color_interfaz("#dbe1e9"), bg=color_interfaz("#171b20"),
                    wrap="word", height=24, width=1, relief="flat", padx=8, pady=8,
                    selectbackground="#cdb8f4", selectforeground="#171717", exportselection=False)
    texto.pack(fill="both", expand=True, padx=20, pady=(0, 24))
    texto.configure(state="disabled")
    texto.bind("<Button-4>", lambda e: (texto.yview_scroll(-3, "units"), "break")[1])
    texto.bind("<Button-5>", lambda e: (texto.yview_scroll(3, "units"), "break")[1])
    texto.tag_configure("marcado", background="#cdb8f4", foreground="#171717", underline=True)

    def poner_texto(cuerpo):
        texto.configure(state="normal")
        for tag in texto.tag_names():
            if tag.startswith("destacado_"):
                texto.tag_remove(tag, "1.0", "end")
        marcador["sobre"] = None
        texto.delete("1.0", "end")
        texto.insert("1.0", cuerpo)
        texto.configure(state="disabled")
        buscar_en_articulo()

    def traducir():
        if lectura["ocupada"] or not lectura["original"]:
            return
        if lectura["traducida"]:
            poner_texto(lectura["original"])
            lectura["traducida"] = False
            boton_traducir.config(text="Leer en español")
            estado_label.config(text=lectura["estado"])
            return
        def aplicar(traduccion):
            if not lector.winfo_exists():
                return
            lectura["ocupada"] = False
            boton_traducir.config(state="normal", text="Leer en español")
            if traduccion is None:
                messagebox.showerror("Traducción", "No se pudo traducir el artículo. Puedes reintentar.")
                return
            lectura["es"] = traduccion
            lectura["traducida"] = True
            poner_texto(traduccion)
            boton_traducir.config(text="Ver original")
            estado_label.config(text="Traducción automática al español")
        if lectura["es"] is not None:
            aplicar(lectura["es"])
            return
        lectura["ocupada"] = True
        boton_traducir.config(state="disabled", text="Traduciendo…")
        original = lectura["original"]
        def trabajo_traduccion():
            bloques = []
            import textwrap
            segmentos = []
            for parrafo in original.split("\n\n"):
                segmentos.extend(textwrap.wrap(parrafo, width=1200, break_long_words=False,
                                              break_on_hyphens=False))
            for segmento in segmentos:
                if not lector.winfo_exists():
                    return
                resultado = traducir_texto(segmento, "es")
                if resultado is None:
                    ventana.after(0, lambda: aplicar(None))
                    return
                bloques.append(resultado)
            ventana.after(0, lambda: aplicar("\n\n".join(bloques)))
        threading.Thread(target=trabajo_traduccion, daemon=True).start()

    nombres_marcador = [n for n in NOMBRES_TEMAS if n != "periodico"]
    marcador = {"color": config.get("color", "gris"), "sobre": None, "activo": False, "ultimo": None}
    if marcador["color"] not in nombres_marcador:
        marcador["color"] = "amarillo_neon"
    for nombre in nombres_marcador:
        texto.tag_configure("destacado_" + nombre,
                            background=PALETA_TEMAS[nombre]["base_fuerte"], foreground="#171717")

    def activar_marcador(activo, nombre=None):
        if nombre:
            marcador["color"] = nombre
        marcador["activo"] = activo
        marcador["ultimo"] = None
        texto.config(cursor="pencil" if activo else "xterm")
        estado_label.config(text="Destacador activo · " + NOMBRES_TEMAS[marcador["color"]]
                           if activo else lectura["estado"])

    def marcar_rango(inicio, fin):
        # Colores mutuamente excluyentes por carácter: no quedan etiquetas
        # solapadas cuya prioridad cambie al elegir otro color.
        for nombre in nombres_marcador:
            texto.tag_remove("destacado_" + nombre, inicio, fin)
        texto.tag_add("destacado_" + marcador["color"], inicio, fin)
        texto.tag_raise("busqueda")
        texto.tag_raise("sel")

    def destacar():
        try:
            marcar_rango(texto.index("sel.first"), texto.index("sel.last"))
        except tk.TclError:
            return

    def quitar_destacado():
        if texto.tag_ranges("sel"):
            inicio, fin = texto.index("sel.first"), texto.index("sel.last")
            for nombre in nombres_marcador:
                texto.tag_remove("destacado_" + nombre, inicio, fin)
        elif marcador["sobre"]:
            tag, inicio, fin = marcador["sobre"]
            texto.tag_remove(tag, inicio, fin)
        marcador["sobre"] = None

    def sobre_destacado(event):
        indice = texto.index(f"@{event.x},{event.y}")
        caja = texto.bbox(indice)
        if not caja or not (caja[0] <= event.x < caja[0] + caja[2] and caja[1] <= event.y < caja[1] + caja[3]):
            # Un hueco entre líneas no interrumpe el trazo mientras se arrastra.
            if not event.state & 0x100:
                marcador["ultimo"] = None
            return
        inicio, fin = texto.index(indice + " wordstart"), texto.index(indice + " wordend")
        if marcador["activo"] and event.state & 0x100 and texto.get(inicio, fin).strip():
            anterior = marcador["ultimo"]
            if anterior:
                # Los índices de texto incluyen todos los caracteres intermedios,
                # incluso al cruzar renglones visuales o párrafos.
                extremos = [anterior[0], anterior[1], inicio, fin]
                extremos.sort(key=lambda i: tuple(map(int, i.split('.'))))
                marcar_rango(extremos[0], extremos[-1])
            else:
                marcar_rango(inicio, fin)
            marcador["ultimo"] = (inicio, fin, caja[1], event.x)
        for tag in texto.tag_names(indice):
            if tag.startswith("destacado_"):
                rango = texto.tag_prevrange(tag, indice + " +1c")
                if rango:
                    marcador["sobre"] = (tag, str(rango[0]), str(rango[1]))
                break
        else:
            marcador["sobre"] = None
    def iniciar_trazo(event):
        if marcador["activo"]:
            indice = texto.index(f"@{event.x},{event.y}")
            inicio, fin = texto.index(indice + " wordstart"), texto.index(indice + " wordend")
            marcador["ultimo"] = (inicio, fin, event.y, event.x)
            texto.tag_remove("sel", "1.0", "end")
            return "break"
    def arrastrar_trazo(event):
        if marcador["activo"]:
            sobre_destacado(event)
            return "break"
    texto.bind("<Button-1>", iniciar_trazo)
    texto.bind("<B1-Motion>", arrastrar_trazo)
    texto.bind("<ButtonRelease-1>", lambda e: marcador.update(ultimo=None))
    texto.bind("<Motion>", sobre_destacado, add="+")
    texto.bind("<Leave>", lambda e: marcador.update(ultimo=None) if not e.state & 0x100 else None, add="+")

    def compartir():
        try:
            inicio, fin = texto.index("sel.first"), texto.index("sel.last")
            fragmento = texto.get(inicio, fin).strip()
        except tk.TclError:
            return
        if not fragmento or len(fragmento) > 500:
            messagebox.showinfo("Crear cita", "Selecciona un fragmento de hasta 500 caracteres.")
            return
        previsualizar_cita(fragmento, articulo, link, lectura["traducida"])

    menu_cita = tk.Menu(texto, tearoff=False, bg=color_interfaz("#232a34"), fg=color_interfaz("#edf1f7"),
                        activebackground="#cdb8f4", activeforeground="#171717",
                        relief="flat", bd=0, font=("Sans", 9))
    menu_cita.add_command(label="Crear imagen de la cita…", command=compartir)
    menu_destacador = tk.Menu(menu_cita, tearoff=False, bg="#232a34", fg="#edf1f7",
                             activebackground="#354052", activeforeground="#ffffff", bd=0)
    for nombre in nombres_marcador:
        menu_destacador.add_command(label="●  " + NOMBRES_TEMAS[nombre],
            foreground=PALETA_TEMAS[nombre]["base_fuerte"],
            command=lambda n=nombre: activar_marcador(True, n))
    menu_destacador.add_command(label="Destacar selección", command=destacar)
    menu_destacador.add_separator()
    menu_destacador.add_command(label="Desactivar destacador", command=lambda: activar_marcador(False))
    menu_cita.add_cascade(label="Destacador", menu=menu_destacador)
    menu_cita.add_command(label="Quitar destacado", command=quitar_destacado)

    def abrir_menu_cita(event):
        marcador["ultimo"] = None
        indice = texto.index(f"@{event.x},{event.y}")
        marcador["sobre"] = None
        for tag in texto.tag_names(indice):
            if tag.startswith("destacado_"):
                rango = texto.tag_prevrange(tag, indice + " +1c")
                if rango:
                    marcador["sobre"] = (tag, str(rango[0]), str(rango[1]))
                break
        try:
            seleccion = texto.get("sel.first", "sel.last").strip()
        except tk.TclError:
            seleccion = ""
        menu_cita.entryconfigure(0, state="normal" if seleccion else "disabled")
        menu_cita.entryconfigure(2, state="normal" if marcador["sobre"] or seleccion else "disabled")
        try:
            menu_cita.tk_popup(event.x_root, event.y_root)
        finally:
            menu_cita.grab_release()
        return "break"

    texto.bind("<Button-3>", lambda event: "break")
    texto.bind("<ButtonRelease-3>", abrir_menu_cita)
    boton_traducir = boton_lectura(acciones_lectura, "Leer en español", traducir, destacado=True)
    boton_traducir.config(state="disabled")
    boton_traducir.pack(side="right", padx=(0, 8))

    buscar_var = tk.StringVar()
    marco_buscar, entrada_buscar = crear_buscador(acciones_lectura, buscar_var, "Buscar en artículo", ancho=180)
    marco_buscar.pack(side="left", fill="x", expand=True, padx=(0, 6))
    entrada_buscar.bind("<FocusIn>", lambda e: activar_marcador(False), add="+")
    texto.tag_configure("busqueda", background=paleta["base_fuerte"],
                        foreground="#ffffff" if config.get("color") == "periodico" else "#171717")
    busqueda = {"rangos": [], "indice": -1}
    def siguiente_resultado(event=None):
        if busqueda["rangos"]:
            busqueda["indice"] = (busqueda["indice"] + 1) % len(busqueda["rangos"])
            inicio = busqueda["rangos"][busqueda["indice"]][0]
            texto.see(f"1.0 + {inicio} chars")
            estado_label.config(text=f"Coincidencia {busqueda['indice'] + 1} de {len(busqueda['rangos'])}")
    def buscar_en_articulo(*args):
        texto.tag_remove("busqueda", "1.0", "end")
        busqueda["rangos"] = coincidencias(texto.get("1.0", "end-1c"), buscar_var.get())
        busqueda["indice"] = -1
        for inicio, fin in busqueda["rangos"]:
            texto.tag_add("busqueda", f"1.0 + {inicio} chars", f"1.0 + {fin} chars")
        texto.tag_raise("busqueda")
        texto.tag_raise("sel")
        if buscar_var.get():
            estado_label.config(text=f"{len(busqueda['rangos'])} coincidencias")
            siguiente_resultado()
    buscar_var.trace_add("write", buscar_en_articulo)
    entrada_buscar.bind("<Return>", siguiente_resultado)

    def ajustar_texto(event):
        for etiqueta in (titulo, estado_label):
            etiqueta.configure(wraplength=max(160, event.width - 40))
        canvas.configure(scrollregion=canvas.bbox("all"))

    lector.bind("<Configure>", ajustar_texto)

    def mostrar(cuerpo, estado):
        if not lector.winfo_exists():
            return
        mostrar_portada()
        poner_texto(cuerpo)
        lectura["estado"] = estado
        if estado != "Contenido no disponible":
            lectura["original"] = cuerpo
            boton_traducir.config(state="normal")
        estado_label.configure(text=estado)
        ajustar_alto_auto()
        canvas.yview_moveto(0)

    vistos.add(link)
    config["vistos"] = list(vistos)
    guardar_config()
    ajustar_alto_auto()
    canvas.yview_moveto(0)

    def cargar():
        cuerpo, estado = contenido_para_articulo(articulo)
        if config.get("mostrar_imagenes_lectura", True) and not articulo.get("imagen"):
            local = biblioteca.leer("descargas", link)
            if local:
                articulo["imagen"] = local.get("imagen")
            elif not lectura_sin_conexion:
                imagen_url = obtener_imagen_og(link)
                if imagen_url:
                    try:
                        articulo["imagen"] = descargar(imagen_url, timeout=8)
                    except Exception:
                        pass
        if not cuerpo:
            cuerpo = "No se pudo recuperar el texto. Puedes consultar el artículo con «Abrir original»."
            estado = "Contenido no disponible"
        else:
            articulo["cuerpo"] = cuerpo
            articulo["estado_contenido"] = estado
        try:
            ventana.after(0, lambda: mostrar(cuerpo, estado))
        except (tk.TclError, RuntimeError):
            pass

    threading.Thread(target=cargar, daemon=True).start()


def titulo_con_busqueda(padre, titulo, tamano, color, ancho):
    rangos = coincidencias(titulo, busqueda_titulos)
    if not rangos:
        return tk.Label(padre, text=titulo, font=("Sans", tamano), fg=color,
                        bg=color_interfaz("#171717"), justify="left", anchor="nw", wraplength=ancho)
    from tkinter import font as tkfont
    fuente = tkfont.Font(family="Sans", size=tamano)
    lineas, linea = 1, ""
    for palabra in re.findall(r"\S+\s*", titulo):
        if linea and fuente.measure(linea + palabra) > ancho:
            lineas += 1
            linea = ""
        linea += palabra
        while fuente.measure(linea) > ancho:
            corte = max(1, len(linea) - 1)
            while corte > 1 and fuente.measure(linea[:corte]) > ancho:
                corte -= 1
            linea = linea[corte:]
            lineas += 1
    etiqueta = tk.Text(padre, font=fuente, height=lineas, width=1, wrap="word", bd=0,
                       highlightthickness=0, padx=0, pady=0, bg=color_interfaz("#171717"), fg=color)
    etiqueta._fuente = fuente
    etiqueta.insert("1.0", titulo)
    etiqueta.tag_configure("encontrado", background=paleta["base_fuerte"],
                           foreground="#ffffff" if config.get("color") == "periodico" else "#171717")
    for inicio, fin in rangos:
        etiqueta.tag_add("encontrado", f"1.0 + {inicio} chars", f"1.0 + {fin} chars")
    etiqueta.configure(state="disabled")
    return etiqueta


def crear_tarjeta_articulo(padre, articulo, fila, columna, ancho, estilo):
    """Portada permanente arriba y texto completo debajo."""
    link = articulo.get("link", "")
    ya_visto = link in vistos
    alto_imagen = estilo["miniatura"]
    alto = estilo["alto"] + alto_imagen

    tarjeta = tk.Frame(padre, bg=color_interfaz("#2a2a2a"), width=ancho, height=alto)
    tarjeta.grid(row=fila, column=columna, sticky="nsew", padx=4, pady=4)
    tarjeta.grid_propagate(False)
    tarjeta.pack_propagate(False)
    tarjeta._es_tarjeta_articulo = True

    interior = tk.Frame(tarjeta, bg=color_interfaz("#171717"))
    interior.pack(fill="both", expand=True, padx=1, pady=1)
    interior.pack_propagate(False)

    portada = tk.Frame(interior, bg=color_interfaz("#222831"), height=alto_imagen)
    portada.pack(fill="x")
    portada.pack_propagate(False)
    imagen = cargar_miniatura_cubierta(articulo.get("imagen"), ancho - 2, alto_imagen)
    if imagen is not None:
        etiqueta_portada = tk.Label(portada, image=imagen, bg=color_interfaz("#222831"), bd=0)
        etiqueta_portada.image = imagen
        etiqueta_portada.pack(fill="both", expand=True)
    else:
        tk.Label(portada, text="Imagen no disponible", font=("Sans", 8),
                 fg=color_interfaz("#8793a3"), bg=color_interfaz("#222831")).pack(expand=True)

    cuerpo = tk.Frame(interior, bg=color_interfaz("#171717"))
    cuerpo.pack(fill="both", expand=True, padx=8, pady=8)

    fuente = tk.Frame(cuerpo, bg=color_interfaz("#171717"))
    fuente.pack(anchor="w", fill="x", pady=(0, 5))
    publicada = fecha_relativa(articulo.get("fecha"))
    if publicada:
        tk.Label(
            fuente,
            text=publicada,
            font=("Sans", max(6, estilo["fuente"] - 1)),
            fg=color_interfaz("#737a82"),
            bg=color_interfaz("#171717"),
            anchor="e"
        ).pack(side="right")
    icono = articulo.get("icono")
    if icono is not None:
        tk.Label(fuente, image=icono, bg=color_interfaz("#171717")).pack(side="left")
    tk.Label(
        fuente,
        text=articulo.get("fuente", "Fuente"),
        font=("Sans", estilo["fuente"], "bold"),
        fg=paleta["base_fuerte"],
        bg=color_interfaz("#171717"),
        anchor="w"
    ).pack(side="left", padx=(6, 0) if icono is not None else 0)

    ancho_texto = max(150, ancho - 28)
    color_titulo = color_interfaz("#707070") if ya_visto else paleta["link"]
    titulo_con_busqueda(cuerpo, articulo.get("titulo", ""), estilo["titulo"], color_titulo,
                        ancho_texto).pack(anchor="w", fill="x")

    titulo_es = articulo.get("titulo_es")
    if titulo_es and articulo.get("traducir_es", False):
        traduccion = tk.Frame(cuerpo, bg=color_interfaz("#171717"))
        traduccion.pack(fill="x", pady=(10, 0))
        # Bandera circular dibujada en Tk: no depende del emoji del sistema.
        bandera = tk.Canvas(traduccion, width=16, height=16, bg=color_interfaz("#171717"),
                            highlightthickness=0, bd=0)
        bandera.pack(side="left", anchor="n", padx=(0, 6), pady=2)
        for y in range(16):
            semiancho = (64 - (y + 0.5 - 8) ** 2) ** 0.5
            color = color_interfaz("#f6c645") if 4 <= y < 12 else color_interfaz("#c9293b")
            bandera.create_line(8 - semiancho, y, 8 + semiancho, y, fill=color)
        bandera.create_rectangle(5, 6, 7, 10, fill=color_interfaz("#b74a43"), outline="")
        titulo_con_busqueda(traduccion, titulo_es, estilo["traducido"],
                            color_interfaz("#707070") if ya_visto else color_interfaz("#b5bcc6"),
                            ancho_texto - 22).pack(side="left", fill="x", expand=True)

    if config.get("radar_activo"):
        distintos, repeticiones = puntuacion_articulo(articulo)
        if distintos:
            tk.Label(cuerpo, text="◎ " * min(3, distintos) + f" Radar · {distintos} intereses · {repeticiones} menciones",
                     bg=color_interfaz("#171717"), fg=paleta["base_fuerte"], font=("Sans", 7)).pack(before=fuente, anchor="w")
    acciones = tk.Frame(cuerpo, bg=color_interfaz("#171717"))
    acciones.pack(fill="x", pady=(10, 0))
    boton_guardar = tk.Button(acciones, text="Quitar guardado" if biblioteca.contiene("guardados", link) else "Guardar",
        command=lambda: alternar_guardado(articulo, boton_guardar), relief="flat", bd=0,
        bg=color_interfaz("#29313d"), fg=paleta["base_fuerte"], font=("Sans", 7), width=32, height=30, cursor="hand2")
    boton_guardar.pack(side="left", padx=(0, 4))
    boton_descargar = tk.Button(acciones, text="Eliminar descarga" if biblioteca.contiene("descargas", link) else "Descargar",
        command=lambda: alternar_descarga(articulo, boton_descargar), relief="flat", bd=0,
        bg=color_interfaz("#29313d"), fg=paleta["base_fuerte"], font=("Sans", 7), width=32, height=30, cursor="hand2")
    boton_descargar.pack(side="left")
    actualizar_icono_archivo(boton_guardar, articulo, "guardados")
    actualizar_icono_archivo(boton_descargar, articulo, "descargas")
    boton_guardar._tipo_archivo = "guardados"
    boton_descargar._tipo_archivo = "descargas"
    cuerpo.update_idletasks()
    tarjeta.configure(height=alto_imagen + cuerpo.winfo_reqheight() + 18)

    def enlazar_click(widget):
        if isinstance(widget, tk.Button):
            return
        widget.configure(cursor="hand2")
        widget.bind("<Button-1>", lambda event: (_abrir_articulo(link, articulo), "break")[1], add="+")
        for hijo in widget.winfo_children():
            enlazar_click(hijo)

    enlazar_click(tarjeta)
    return tarjeta


def mostrar_articulos_en_tarjetas(articulos):
    """Filtra títulos y ordena por intereses sin descargar durante el dibujo."""
    articulos = [a for a in articulos if not busqueda_titulos or
                 coincidencias(a.get("titulo", "") + " " + (a.get("titulo_es") or ""), busqueda_titulos)]
    if config.get("radar_activo"):
        articulos = sorted(articulos, key=puntuacion_articulo, reverse=True)
    if not articulos:
        cargando = vista_actual not in {"guardados", "descargas"} and actualizacion_en_curso
        mensaje = "Cargando artículos e imágenes…" if cargando else ("No hay títulos que coincidan." if busqueda_titulos else "No hay artículos en esta sección.")
        tk.Label(contenido, text=mensaje, wraplength=max(200, ancho_usable_actual() - 40),
                 font=("Sans", 9), fg=color_interfaz("#888888"), bg=color_interfaz("#111315")).pack(anchor="center", pady=(12, 0))
        return

    ancho_ventana = ancho_usable_actual()
    columnas = columnas_para_ancho(ancho_ventana)
    estilo = estilo_tarjeta_por_columnas(columnas)
    ancho_tarjeta = max(180, int((ancho_ventana - 90) / columnas)) if columnas > 1 else ancho_ventana - 60
    grilla = tk.Frame(contenido, bg=color_interfaz("#111315"))
    grilla.pack(fill="x", pady=(0, 10))
    for columna in range(columnas):
        grilla.grid_columnconfigure(columna, weight=1)

    for indice, articulo in enumerate(articulos):
        crear_tarjeta_articulo(
            grilla, articulo, indice // columnas, indice % columnas,
            ancho_tarjeta, estilo
        )


def mostrar_fuentes_sin_feed(categoria):
    """Muestra fuentes guardadas que aún no disponen de un RSS utilizable."""
    fuentes = [sitio for sitio in categoria.get("sitios", []) if not sitio.get("url_feed")]
    if not fuentes:
        return

    bloque = tk.Frame(contenido, bg=color_interfaz("#111315"))
    bloque.pack(fill="x", pady=(0, 9))
    tk.Label(
        bloque, text="FUENTES SIN FEED", font=("Sans", 6, "bold"),
        fg=color_interfaz("#777f89"), bg=color_interfaz("#111315")
    ).pack(anchor="w", padx=4, pady=(0, 4))

    for sitio in fuentes:
        # Marco fijo y pequeño, distinto de las tarjetas de artículos.
        ficha = tk.Frame(bloque, bg=color_interfaz("#30363e"), height=36, cursor="hand2")
        ficha.pack(fill="x", pady=2)
        ficha.pack_propagate(False)
        interior = tk.Frame(ficha, bg=color_interfaz("#1a1c20"), cursor="hand2")
        interior.pack(fill="both", expand=True, padx=1, pady=1)

        icono = obtener_imagen_favicon(sitio)
        if icono is not None:
            tk.Label(interior, image=icono, bg=color_interfaz("#1a1c20"), cursor="hand2").pack(side="left", padx=(8, 6))
        tk.Label(
            interior, text=sitio.get("nombre", "Fuente"), font=("Sans", 8, "bold"),
            fg=color_interfaz("#d4d9de"), bg=color_interfaz("#1a1c20"), cursor="hand2"
        ).pack(side="left")
        tk.Label(
            interior, text="Sin feed · Abrir sitio ↗", font=("Sans", 7),
            fg=color_interfaz("#7f8994"), bg=color_interfaz("#1a1c20"), cursor="hand2"
        ).pack(side="right", padx=9)

        enlace = sitio.get("url", "")
        def abrir_sitio(event=None, url=enlace):
            if url:
                webbrowser.open(url)
            return "break"

        def enlazar(widget):
            widget.bind("<Button-1>", abrir_sitio, add="+")
            for hijo in widget.winfo_children():
                enlazar(hijo)

        enlazar(ficha)


def actualizar_hover_tarjeta(event=None):
    """Aplica color exclusivamente al borde de la tarjeta bajo el cursor."""
    global tarjeta_hover_actual
    try:
        widget = ventana.winfo_containing(event.x_root, event.y_root)
        nueva_tarjeta = None
        while widget is not None:
            if getattr(widget, "_es_tarjeta_articulo", False):
                nueva_tarjeta = widget
                break
            widget = widget.master
    except (AttributeError, tk.TclError):
        nueva_tarjeta = None

    if nueva_tarjeta is tarjeta_hover_actual:
        return

    if tarjeta_hover_actual is not None:
        try:
            tarjeta_hover_actual.configure(bg=color_interfaz("#2a2a2a"))
        except tk.TclError:
            pass

    tarjeta_hover_actual = nueva_tarjeta
    if nueva_tarjeta is not None:
        try:
            nueva_tarjeta.configure(bg=paleta["base"])
        except tk.TclError:
            tarjeta_hover_actual = None


def vista_lectura():
    """Vista de lectura basada únicamente en el nuevo renderizador de tarjetas."""
    posicion_scroll = canvas.yview()[0]
    panel_busqueda.pack(fill="x", before=area_desplazable, padx=14, pady=(10, 0))
    limpiar_contenido()
    referencias_imagenes_articulos.clear()

    refrescar_menu_lateral()

    if vista_actual in {"guardados", "descargas"}:
        tk.Label(contenido, text="Guardados" if vista_actual == "guardados" else "Descargas · Sin conexión",
                 bg=color_interfaz("#111315"), fg=paleta["base_fuerte"], font=("Sans", 12, "bold")).pack(anchor="w", pady=10)
        mostrar_articulos_en_tarjetas(biblioteca.listar(vista_actual))
    elif vista_actual == "fuente" and categoria_activa:
        categoria = next((c for c in config["categorias"] if c["nombre"] == categoria_activa), None)
        fuente = next((f for f in categoria.get("sitios", []) if f["url"] == fuente_activa), None) if categoria else None
        if fuente is None:
            navegar_menu()
            return
        tk.Label(contenido, text=fuente["nombre"], font=("Sans", 10, "bold"),
                 fg=paleta["base_fuerte"], bg=color_interfaz("#111315")).pack(anchor="w", pady=(4, 8))
        mostrar_fuentes_sin_feed({"sitios": [fuente]})
        if datos_articulos.get(fuente_activa) == "cargando":
            tk.Label(contenido, text="Cargando artículos…", fg=color_interfaz("#8b9198"),
                     bg=color_interfaz("#111315"), font=("Sans", 9)).pack(pady=12)
        else:
            mostrar_articulos_en_tarjetas(articulos_combinados_categoria(categoria_activa, fuente_activa))
    elif vista_actual == "categoria" and categoria_activa:
        categoria = next((c for c in config["categorias"] if c.get("nombre") == categoria_activa), None)
        tk.Label(
            contenido, text=categoria_activa, font=("Sans", 10, "bold"),
            fg=color_interfaz("#f2f2f2"), bg=color_interfaz("#111315")
        ).pack(anchor="center", pady=(4, 8))
        tk.Frame(contenido, bg=color_interfaz("#3a3d41"), height=1).pack(fill="x", pady=(0, 8))
        if categoria is not None:
            mostrar_fuentes_sin_feed(categoria)
        mostrar_articulos_en_tarjetas(articulos_combinados_categoria(categoria_activa))
    elif filtro_principal == "todo":
        mostrar_articulos_en_tarjetas(articulos_combinados_ver_todo())
    else:
        # La portada de categorías conserva su navegación, sin reutilizar
        # ninguna tarjeta de artículo.
        for categoria in config["categorias"]:
            nombre = categoria["nombre"]
            fila = tk.Frame(contenido, bg=color_interfaz("#111315"), cursor="hand2")
            fila.pack(fill="x")
            tk.Label(fila, text=nombre, font=("Sans", 9, "bold"), fg=color_interfaz("#dfe3e7"), bg=color_interfaz("#111315")).pack(anchor="center", pady=(10, 2))
            tk.Label(fila, text=f"{len(categoria['sitios'])} fuentes", font=("Sans", 7), fg=color_interfaz("#8b9198"), bg=color_interfaz("#111315")).pack(anchor="center", pady=(0, 10))
            for widget in (fila, *fila.winfo_children()):
                widget.bind("<Button-1>", lambda event, n=nombre: seleccionar_categoria(n))
            tk.Frame(contenido, bg=color_interfaz("#2a2d31"), height=1).pack(fill="x")

    pie_estado.config(text="Última actualización: " + datetime.now().strftime("%H:%M"))
    ajustar_alto_auto()
    canvas.yview_moveto(posicion_scroll)


# ============================================================
# ACTUALIZACIÓN EN SEGUNDO PLANO
# ============================================================

def actualizar_sitios_en_segundo_plano(lista_de_sitios):

    global actualizacion_en_curso
    if actualizacion_en_curso or not lista_de_sitios:
        return

    actualizacion_en_curso = True
    pie_estado.config(text="Actualizando…")
    refrescar_vista()

    def trabajo():
        resultados = {}
        fuentes = {s["url"]: s for s in lista_de_sitios}

        def cargar_fuente(sitio_actual):
            resultados = {}
            url_sitio = sitio_actual["url"]

            url_feed = sitio_actual.get("url_feed")

            if not url_feed:

                url_feed = descubrir_feed(url_sitio)

                if url_feed:
                    sitio_actual["url_feed"] = url_feed

            ruta_icono = descargar_favicon(url_sitio)

            if ruta_icono:
                rutas_favicon[url_sitio] = ruta_icono

            if not url_feed:
                resultados[url_sitio] = datos_articulos.get(url_sitio) if isinstance(datos_articulos.get(url_sitio), list) else None
                sitio_actual["ultima_actualizacion"] = time.time()
                return resultados[url_sitio]

            maximo = sitio_actual.get("max_articulos") or ARTICULOS_POR_SITIO

            articulos_crudos = obtener_articulos(url_feed, maximo=maximo)

            if articulos_crudos is None:
                resultados[url_sitio] = datos_articulos.get(url_sitio) if isinstance(datos_articulos.get(url_sitio), list) else None
                sitio_actual["ultima_actualizacion"] = time.time()
                return resultados[url_sitio]

            con_traduccion = []

            for titulo, link, imagen_url, fecha_texto in articulos_crudos:

                traduccion = (
                    traducir_texto(titulo, "es")
                    if mostrar_titulo_traducido_sitio(sitio_actual)
                    else None
                )

                imagen_bytes = None

                # La portada forma parte de todas las tarjetas, independientemente
                # de la antigua preferencia de miniaturas de cada fuente.
                candidatos = [urllib.parse.urljoin(link, imagen_url)] if imagen_url else []
                for imagen_candidata in candidatos:
                    try:
                        imagen_bytes = descargar(unescape(imagen_candidata), timeout=8)
                        if PIL_DISPONIBLE:
                            with Image.open(io.BytesIO(imagen_bytes)) as prueba:
                                prueba.verify()
                    except Exception:
                        imagen_bytes = None
                if not imagen_bytes:
                    imagen_og = obtener_imagen_og(link)
                    if imagen_og:
                        try:
                            imagen_bytes = descargar(imagen_og, timeout=8)
                        except Exception:
                            pass

                con_traduccion.append((titulo, link, traduccion, imagen_bytes, fecha_texto))

            resultados[url_sitio] = con_traduccion
            sitio_actual["ultima_actualizacion"] = time.time()

            return con_traduccion

        with ThreadPoolExecutor(max_workers=6) as ejecutor:
            tareas = {ejecutor.submit(cargar_fuente, fuente): url for url, fuente in fuentes.items()}
            for numero, tarea in enumerate(as_completed(tareas), 1):
                url = tareas[tarea]
                try:
                    resultados[url] = tarea.result()
                except Exception as error:
                    print(f"[noticias] Error cargando {url}: {error}")
                    anteriores = datos_articulos.get(url)
                    resultados[url] = anteriores if isinstance(anteriores, list) else None
                ventana.after(0, lambda n=numero: pie_estado.config(
                    text=f"Cargando fuentes: {n}/{len(fuentes)}"))

        def publicar():
            global actualizacion_en_curso
            datos_articulos.update(resultados)
            actualizacion_en_curso = False
            guardar_config()
            refrescar_vista()
            pie_estado.config(text="Última actualización: " + datetime.now().strftime("%H:%M"))
            analizar_radar()

        ventana.after(0, publicar)

    def ejecutar_actualizacion():
        try:
            trabajo()
        except Exception as error:
            print(f"[noticias] Error actualizando el feed: {error}")
            def informar_error():
                global actualizacion_en_curso
                actualizacion_en_curso = False
                pie_estado.config(text="Error al actualizar · Puedes reintentar")
            try:
                ventana.after(0, informar_error)
            except (tk.TclError, RuntimeError):
                pass

    hilo = threading.Thread(target=ejecutar_actualizacion, daemon=True)
    hilo.start()


def todos_los_sitios():

    return [s for c in config["categorias"] for s in c["sitios"]]


def actualizar_todo_manual():

    actualizar_sitios_en_segundo_plano(todos_los_sitios())


actualizar_btn.bind("<Button-1>", lambda event: actualizar_todo_manual())


# ============================================================
# VISTA: ADMINISTRAR
# ============================================================

def nombres_categorias():

    return [c["nombre"] for c in config["categorias"]]


def categorias_duplicadas_de_fuente(url_sitio, categoria_actual):
    """Devuelve las otras categorías que contienen la misma URL de fuente."""
    return [
        categoria["nombre"]
        for categoria in config["categorias"]
        if categoria["nombre"] != categoria_actual
        and any(sitio.get("url") == url_sitio for sitio in categoria.get("sitios", []))
    ]


def mover_categoria(indice, direccion):

    nuevo = indice + direccion

    if 0 <= nuevo < len(config["categorias"]):

        config["categorias"][indice], config["categorias"][nuevo] = (
            config["categorias"][nuevo], config["categorias"][indice]
        )

        guardar_config()
        vista_admin()


def borrar_categoria(indice):

    if config["categorias"][indice]["sitios"]:

        mensaje_admin.config(
            text="Esa categoría tiene sitios. Muévelos o bórralos primero."
        )

        return

    config["categorias"].pop(indice)
    guardar_config()
    vista_admin()


def mover_sitio(nombre_cat, indice, direccion):

    for categoria in config["categorias"]:

        if categoria["nombre"] != nombre_cat:
            continue

        nuevo = indice + direccion

        if 0 <= nuevo < len(categoria["sitios"]):

            categoria["sitios"][indice], categoria["sitios"][nuevo] = (
                categoria["sitios"][nuevo], categoria["sitios"][indice]
            )

            guardar_config()
            vista_admin()

        return


def borrar_sitio(nombre_cat, indice):

    for categoria in config["categorias"]:

        if categoria["nombre"] == nombre_cat:
            categoria["sitios"].pop(indice)
            guardar_config()
            vista_admin()
            return


def mover_sitio_a_categoria(nombre_cat_origen, indice, nombre_cat_destino):

    if nombre_cat_origen == nombre_cat_destino:
        return

    categoria_origen = None
    categoria_destino = None

    for categoria in config["categorias"]:

        if categoria["nombre"] == nombre_cat_origen:
            categoria_origen = categoria

        if categoria["nombre"] == nombre_cat_destino:
            categoria_destino = categoria

    if categoria_origen is None or categoria_destino is None:
        return

    sitio_movido = categoria_origen["sitios"].pop(indice)
    categoria_destino["sitios"].append(sitio_movido)

    guardar_config()
    vista_admin()


def agregar_categoria(entry_nombre):

    nombre = entry_nombre.get().strip()

    if not nombre:
        return

    if nombre in nombres_categorias():

        mensaje_admin.config(text="Ya existe una categoría con ese nombre.")
        return

    config["categorias"].append({"nombre": nombre, "sitios": []})
    guardar_config()
    vista_admin()


def guardar_nombre_categoria(categoria, entry_nombre):

    nombre = entry_nombre.get().strip()

    if not nombre:
        return

    if nombre == categoria["nombre"]:
        return

    if nombre in nombres_categorias():
        mensaje_admin.config(text="Ya existe una categoría con ese nombre.")
        return

    categoria["nombre"] = nombre
    guardar_config()
    vista_admin()


def agregar_sitio(nombre_cat, entry_nombre, entry_url, etiqueta_estado):

    nombre = entry_nombre.get().strip()
    url = entry_url.get().strip()

    if not nombre or not url:

        etiqueta_estado.config(text="Completa nombre y URL.", fg=color_interfaz("#a05050"))
        return

    if not url.startswith("http"):
        url = "https://" + url

    etiqueta_estado.config(text="Buscando feed…", fg=color_interfaz("#888888"))

    def trabajo():

        url_feed = url if obtener_articulos(url, silencioso=True) is not None else descubrir_feed(url)

        def terminar():

            for categoria in config["categorias"]:

                if categoria["nombre"] == nombre_cat:

                    nuevo_sitio = sitio(nombre, url)
                    nuevo_sitio["url_feed"] = url_feed

                    categoria["sitios"].append(nuevo_sitio)

                    guardar_config()

            if url_feed is None:

                mensaje_admin.config(
                    text=f"Se agregó '{nombre}', pero no se pudo detectar su feed."
                )

            vista_admin()

        ventana.after(0, terminar)

    threading.Thread(target=trabajo, daemon=True).start()


def vista_admin():
    panel_busqueda.pack_forget()
    global paleta, seccion_config
    paleta = tema_actual()
    refrescar_menu_lateral()

    limpiar_contenido()

    encabezado = tk.Frame(contenido, bg=color_interfaz("#171717"))
    encabezado.pack(fill="x", pady=(0, 12))

    titulos_seccion = {
        "diseño": "Diseño",
        "radar": "Radar de intereses",
        "categorias": "Categorías",
        "fuentes": "Fuentes",
    }

    tk.Label(
        encabezado, text=titulos_seccion.get(seccion_config, "Configuración"), font=("Sans", 9, "bold"),
        fg=color_interfaz("#d0d0d0"), bg=color_interfaz("#171717")
    ).pack(side="left")

    global mensaje_admin

    mensaje_admin = tk.Label(
        contenido, text="", font=("Sans", 7), fg=color_interfaz("#a05050"), bg=color_interfaz("#171717"),
        wraplength=ancho_actual - 40, justify="left"
    )

    mensaje_admin.pack(anchor="w", pady=(0, 6))

    # Contenido según la sección seleccionada
    if seccion_config == "diseño":
        vista_seccion_diseño()
    elif seccion_config == "radar":
        vista_seccion_radar()
    elif seccion_config == "categorias":
        vista_seccion_categorias()
    elif seccion_config == "fuentes":
        vista_seccion_fuentes()

    ajustar_alto_auto()

def cambiar_seccion_config(seccion):
    global seccion_config
    seccion_config = seccion
    refrescar_vista_con_carga(lambda: vista_admin())


def crear_dialogo(titulo, ancho=400):
    dialogo = tk.Toplevel(ventana)
    dialogo.title(titulo)
    dialogo.configure(bg=color_interfaz("#17191d"))
    dialogo.transient(ventana)
    dialogo.resizable(False, False)
    dialogo.attributes("-topmost", True)
    dialogo.geometry(f"+{ventana.winfo_x() + 30}+{ventana.winfo_y() + 60}")
    return dialogo


def campo_dialogo(padre, titulo, valor=""):
    tk.Label(padre, text=titulo, font=("Sans", 8, "bold"), fg=color_interfaz("#cbd2da"), bg=color_interfaz("#17191d")).pack(anchor="w", pady=(10, 4))
    entrada = tk.Entry(
        padre, bg=color_interfaz("#252a30"), fg=color_interfaz("#edf1f5"), insertbackground=color_interfaz("#edf1f5"),
        relief="flat", font=("Sans", 9)
    )
    entrada.insert(0, valor)
    entrada.pack(fill="x", ipady=6)
    return entrada


def abrir_dialogo_agregar_categoria():
    dialogo = crear_dialogo("Nueva categoría", 360)
    cuerpo = tk.Frame(dialogo, bg=color_interfaz("#17191d"), padx=18, pady=16)
    cuerpo.pack(fill="both", expand=True)
    tk.Label(cuerpo, text="Nueva categoría", font=("Sans", 11, "bold"), fg=color_interfaz("#edf1f5"), bg=color_interfaz("#17191d")).pack(anchor="w")
    tk.Label(cuerpo, text="Organiza tus fuentes en grupos.", font=("Sans", 8), fg=color_interfaz("#8f99a5"), bg=color_interfaz("#17191d")).pack(anchor="w", pady=(3, 0))
    entrada_nombre = campo_dialogo(cuerpo, "NOMBRE DE LA CATEGORÍA")
    estado = tk.Label(cuerpo, text="", font=("Sans", 8), fg=color_interfaz("#dc7b7b"), bg=color_interfaz("#17191d"))
    estado.pack(anchor="w", pady=(8, 0))

    def guardar():
        nombre = entrada_nombre.get().strip()
        if not nombre:
            estado.config(text="Escribe un nombre para continuar.")
            return
        if nombre in nombres_categorias():
            estado.config(text="Ya existe una categoría con ese nombre.")
            return
        config["categorias"].append({"nombre": nombre, "sitios": []})
        guardar_config()
        dialogo.destroy()
        vista_admin()

    acciones = tk.Frame(cuerpo, bg=color_interfaz("#17191d"))
    acciones.pack(fill="x", pady=(14, 0))
    cancelar = tk.Label(acciones, text="Cancelar", font=("Sans", 8), fg=color_interfaz("#9aa4b2"), bg=color_interfaz("#17191d"), cursor="hand2", padx=10, pady=7)
    cancelar.pack(side="right")
    cancelar.bind("<Button-1>", lambda event: dialogo.destroy())
    guardar_btn = tk.Label(acciones, text="Crear categoría", font=("Sans", 8, "bold"), fg=color_interfaz("#111315"), bg=paleta["base"], cursor="hand2", padx=12, pady=7)
    guardar_btn.pack(side="right", padx=(0, 6))
    guardar_btn.bind("<Button-1>", lambda event: guardar())
    entrada_nombre.focus_set()


def abrir_dialogo_editar_categoria(categoria):
    dialogo = crear_dialogo("Editar categoría", 360)
    cuerpo = tk.Frame(dialogo, bg=color_interfaz("#17191d"), padx=18, pady=16)
    cuerpo.pack(fill="both", expand=True)
    tk.Label(cuerpo, text="Editar categoría", font=("Sans", 11, "bold"), fg=color_interfaz("#edf1f5"), bg=color_interfaz("#17191d")).pack(anchor="w")
    entrada_nombre = campo_dialogo(cuerpo, "NOMBRE DE LA CATEGORÍA", categoria["nombre"])
    estado = tk.Label(cuerpo, text="", font=("Sans", 8), fg=color_interfaz("#dc7b7b"), bg=color_interfaz("#17191d"))
    estado.pack(anchor="w", pady=(8, 0))

    def guardar():
        nombre = entrada_nombre.get().strip()
        if not nombre:
            estado.config(text="Escribe un nombre para continuar.")
        elif nombre != categoria["nombre"] and nombre in nombres_categorias():
            estado.config(text="Ya existe una categoría con ese nombre.")
        else:
            categoria["nombre"] = nombre
            guardar_config()
            dialogo.destroy()
            vista_admin()

    acciones = tk.Frame(cuerpo, bg=color_interfaz("#17191d"))
    acciones.pack(fill="x", pady=(14, 0))
    tk.Label(acciones, text="Cancelar", font=("Sans", 8), fg=color_interfaz("#9aa4b2"), bg=color_interfaz("#17191d"), cursor="hand2", padx=10, pady=7).pack(side="right")
    cancelar = acciones.winfo_children()[-1]
    cancelar.bind("<Button-1>", lambda event: dialogo.destroy())
    guardar_btn = tk.Label(acciones, text="Guardar", font=("Sans", 8, "bold"), fg=color_interfaz("#111315"), bg=paleta["base"], cursor="hand2", padx=12, pady=7)
    guardar_btn.pack(side="right", padx=(0, 6))
    guardar_btn.bind("<Button-1>", lambda event: guardar())
    entrada_nombre.focus_set()


def abrir_dialogo_agregar_fuente(categoria_preseleccionada=None):
    dialogo = crear_dialogo("Nueva fuente", 440)
    cuerpo = tk.Frame(dialogo, bg=color_interfaz("#17191d"), padx=18, pady=16)
    cuerpo.pack(fill="both", expand=True)
    tk.Label(cuerpo, text="Nueva fuente", font=("Sans", 11, "bold"), fg=color_interfaz("#edf1f5"), bg=color_interfaz("#17191d")).pack(anchor="w")
    tk.Label(cuerpo, text="Añade una web y encontraremos su feed automáticamente.", font=("Sans", 8), fg=color_interfaz("#8f99a5"), bg=color_interfaz("#17191d")).pack(anchor="w", pady=(3, 0))
    entrada_nombre = campo_dialogo(cuerpo, "NOMBRE")
    entrada_url = campo_dialogo(cuerpo, "URL DE LA WEB O FEED")
    tk.Label(cuerpo, text="CATEGORÍA", font=("Sans", 8, "bold"), fg=color_interfaz("#cbd2da"), bg=color_interfaz("#17191d")).pack(anchor="w", pady=(10, 4))
    categoria_elegida = tk.StringVar(value=categoria_preseleccionada or (nombres_categorias()[0] if nombres_categorias() else ""))
    selector_categoria = tk.OptionMenu(cuerpo, categoria_elegida, *nombres_categorias())
    selector_categoria.config(bg=color_interfaz("#252a30"), fg=color_interfaz("#edf1f5"), highlightthickness=0, font=("Sans", 8), bd=0)
    selector_categoria["menu"].config(bg=color_interfaz("#252a30"), fg=color_interfaz("#edf1f5"), font=("Sans", 8))
    selector_categoria.pack(anchor="w")

    estado = tk.Label(cuerpo, text="", font=("Sans", 8), fg=color_interfaz("#dc7b7b"), bg=color_interfaz("#17191d"))
    estado.pack(anchor="w", pady=(8, 0))

    def guardar():
        nombre, url, categoria = entrada_nombre.get().strip(), entrada_url.get().strip(), categoria_elegida.get()
        if not nombre or not url or not categoria:
            estado.config(text="Completa nombre, URL y categoría.")
            return
        if not url.startswith("http"):
            url = "https://" + url
        estado.config(text="Buscando feed…", fg=color_interfaz("#9aa4b2"))
        guardar_btn.unbind("<Button-1>")

        def trabajo():
            url_feed = url if obtener_articulos(url, silencioso=True) is not None else descubrir_feed(url)

            def terminar():
                categoria_destino = next((c for c in config["categorias"] if c["nombre"] == categoria), None)
                if categoria_destino is None:
                    return
                nueva_fuente = sitio(nombre, url)
                nueva_fuente["url_feed"] = url_feed
                categoria_destino["sitios"].append(nueva_fuente)
                guardar_config()
                datos_articulos[url] = "cargando"
                dialogo.destroy()
                vista_admin()
                pie_estado.config(text="Fuente añadida · Pulsa Actualizar feed")

            ventana.after(0, terminar)

        threading.Thread(target=trabajo, daemon=True).start()

    acciones = tk.Frame(cuerpo, bg=color_interfaz("#17191d"))
    acciones.pack(fill="x", pady=(14, 0))
    cancelar = tk.Label(acciones, text="Cancelar", font=("Sans", 8), fg=color_interfaz("#9aa4b2"), bg=color_interfaz("#17191d"), cursor="hand2", padx=10, pady=7)
    cancelar.pack(side="right")
    cancelar.bind("<Button-1>", lambda event: dialogo.destroy())
    guardar_btn = tk.Label(acciones, text="Añadir fuente", font=("Sans", 8, "bold"), fg=color_interfaz("#111315"), bg=paleta["base"], cursor="hand2", padx=12, pady=7)
    guardar_btn.pack(side="right", padx=(0, 6))
    guardar_btn.bind("<Button-1>", lambda event: guardar())
    entrada_nombre.focus_set()


def abrir_dialogo_editar_fuente(sitio_actual):
    dialogo = crear_dialogo("Editar fuente", 460)
    cuerpo = tk.Frame(dialogo, bg=color_interfaz("#17191d"), padx=18, pady=16)
    cuerpo.pack(fill="both", expand=True)
    tk.Label(cuerpo, text=sitio_actual["nombre"], font=("Sans", 11, "bold"), fg=color_interfaz("#edf1f5"), bg=color_interfaz("#17191d")).pack(anchor="w")
    tk.Label(cuerpo, text="Configuración de la fuente", font=("Sans", 8), fg=color_interfaz("#8f99a5"), bg=color_interfaz("#17191d")).pack(anchor="w", pady=(3, 0))
    entrada_link = campo_dialogo(cuerpo, "URL DEL FEED", sitio_actual.get("url_feed") or sitio_actual["url"])

    ajustes = tk.Frame(cuerpo, bg=color_interfaz("#17191d"))
    ajustes.pack(fill="x", pady=(12, 0))
    ajustes.grid_columnconfigure(0, weight=1)
    ajustes.grid_columnconfigure(1, weight=1)

    def tarjeta_ajuste(columna, titulo, descripcion):
        tarjeta = tk.Frame(ajustes, bg=color_interfaz("#252a30"), highlightbackground=color_interfaz("#343b44"), highlightthickness=1)
        tarjeta.grid(row=0, column=columna, sticky="nsew", padx=(0, 5) if columna == 0 else (5, 0))
        tk.Label(tarjeta, text=titulo, font=("Sans", 8, "bold"), fg=color_interfaz("#e0e3e7"), bg=color_interfaz("#252a30")).pack(anchor="w", padx=9, pady=(8, 2))
        tk.Label(tarjeta, text=descripcion, font=("Sans", 7), fg=color_interfaz("#8f99a5"), bg=color_interfaz("#252a30"), wraplength=175).pack(anchor="w", padx=9)
        return tarjeta

    tarjeta_max = tarjeta_ajuste(0, "Artículos a mostrar", "Cantidad cargada en cada actualización.")
    entrada_max = tk.Entry(tarjeta_max, bg=color_interfaz("#1a1c20"), fg=color_interfaz("#edf1f5"), insertbackground=color_interfaz("#edf1f5"), relief="flat", font=("Sans", 9), width=5)
    entrada_max.insert(0, str(sitio_actual.get("max_articulos") or ARTICULOS_POR_SITIO))
    entrada_max.pack(anchor="w", padx=9, pady=(7, 9), ipady=4)
    tarjeta_intervalo = tarjeta_ajuste(1, "Actualizar cada", "Intervalo en minutos para consultar el feed.")
    entrada_intervalo = tk.Entry(tarjeta_intervalo, bg=color_interfaz("#1a1c20"), fg=color_interfaz("#edf1f5"), insertbackground=color_interfaz("#edf1f5"), relief="flat", font=("Sans", 9), width=5)
    entrada_intervalo.insert(0, str(sitio_actual.get("intervalo_min") or MINUTOS_ENTRE_ACTUALIZACIONES))
    entrada_intervalo.pack(anchor="w", padx=9, pady=(7, 9), ipady=4)

    opciones = tk.Frame(cuerpo, bg=color_interfaz("#252a30"), highlightbackground=color_interfaz("#343b44"), highlightthickness=1)
    opciones.pack(fill="x", pady=(10, 0))
    var_imagen = tk.BooleanVar(value=sitio_actual.get("mostrar_imagen", False))
    tk.Checkbutton(opciones, text="Mostrar miniaturas", variable=var_imagen, font=("Sans", 8), fg=color_interfaz("#d4d9de"), bg=color_interfaz("#252a30"), activebackground=color_interfaz("#252a30"), activeforeground=color_interfaz("#edf1f5"), selectcolor=color_interfaz("#1a1c20"), highlightthickness=0, bd=0).pack(side="left", padx=8, pady=8)
    var_modo = tk.StringVar(value=sitio_actual.get("modo_titulo", "en_es"))
    selector_modo = tk.OptionMenu(opciones, var_modo, "en_es", "solo_ingles")
    selector_modo.config(bg=color_interfaz("#1a1c20"), fg=color_interfaz("#d4d9de"), highlightthickness=0, bd=0, font=("Sans", 7))
    selector_modo["menu"].config(bg=color_interfaz("#1a1c20"), fg=color_interfaz("#d4d9de"), font=("Sans", 7))
    selector_modo.pack(side="right", padx=8, pady=6)

    estado = tk.Label(cuerpo, text="", font=("Sans", 8), fg=color_interfaz("#dc7b7b"), bg=color_interfaz("#17191d"))
    estado.pack(anchor="w", pady=(8, 0))
    def guardar():
        link = entrada_link.get().strip()
        if not link:
            estado.config(text="La URL del feed no puede estar vacía.")
            return
        if not link.startswith("http"):
            link = "https://" + link
        if not entrada_max.get().strip().isdigit() or not entrada_intervalo.get().strip().isdigit():
            estado.config(text="Los valores numéricos deben ser enteros.")
            return
        recargar = link != (sitio_actual.get("url_feed") or "") or int(entrada_max.get()) != (sitio_actual.get("max_articulos") or ARTICULOS_POR_SITIO) or var_imagen.get() != sitio_actual.get("mostrar_imagen", False)
        sitio_actual["url_feed"] = link
        sitio_actual["max_articulos"] = int(entrada_max.get())
        sitio_actual["intervalo_min"] = int(entrada_intervalo.get())
        sitio_actual["mostrar_imagen"] = var_imagen.get()
        sitio_actual["modo_titulo"] = var_modo.get()
        guardar_config()
        dialogo.destroy()
        if recargar:
            pie_estado.config(text="Cambios guardados · Pulsa Actualizar feed")
        vista_admin()
    acciones = tk.Frame(cuerpo, bg=color_interfaz("#17191d"))
    acciones.pack(fill="x", pady=(14, 0))
    cancelar = tk.Label(acciones, text="Cancelar", font=("Sans", 8), fg=color_interfaz("#9aa4b2"), bg=color_interfaz("#17191d"), cursor="hand2", padx=10, pady=7)
    cancelar.pack(side="right")
    cancelar.bind("<Button-1>", lambda event: dialogo.destroy())
    guardar_btn = tk.Label(acciones, text="Guardar cambios", font=("Sans", 8, "bold"), fg=color_interfaz("#111315"), bg=paleta["base"], cursor="hand2", padx=12, pady=7)
    guardar_btn.pack(side="right", padx=(0, 6))
    guardar_btn.bind("<Button-1>", lambda event: guardar())

def vista_seccion_radar():
    preferencias = tk.Frame(contenido, bg=color_interfaz("#1b1d20"))
    preferencias.pack(fill="x", pady=12)
    tk.Label(preferencias, text="Radar · palabras o frases separadas por comas", bg=color_interfaz("#1b1d20"),
             fg=paleta["texto"]).pack(anchor="w", padx=10)
    palabras_radar = tk.Entry(preferencias, bg=color_interfaz("#29313d"), fg=paleta["texto"], relief="flat")
    palabras_radar.insert(0, ", ".join(config.get("radar_palabras", [])))
    palabras_radar.pack(fill="x", padx=10, pady=8)
    def guardar_radar():
        config["radar_palabras"] = list(dict.fromkeys(p.strip() for p in palabras_radar.get().split(",") if p.strip()))
        guardar_config()
        analizar_radar()
    tk.Button(preferencias, text="Guardar intereses", command=guardar_radar, bg=color_interfaz("#29313d"),
              fg=paleta["base_fuerte"], relief="flat").pack(anchor="w", padx=10, pady=(0, 8))
    tk.Label(preferencias, text="Prioridad: intereses distintos y luego número de menciones. 1, 2 o 3 radares (3 o más intereses).",
             wraplength=350, justify="left", bg=color_interfaz("#1b1d20"), fg=paleta["texto_sec"]).pack(anchor="w", padx=10, pady=(0, 8))


def vista_seccion_diseño():
    global paleta
    paleta = tema_actual()

    preferencias = tk.Frame(contenido, bg=color_interfaz("#1b1d20"))
    preferencias.pack(fill="x", pady=(0, 12))
    imagenes_var = tk.BooleanVar(value=config.get("mostrar_imagenes_lectura", True))
    def guardar_imagenes():
        config["mostrar_imagenes_lectura"] = imagenes_var.get()
        guardar_config()
    tk.Checkbutton(preferencias, text="Mostrar imágenes dentro de los artículos", variable=imagenes_var,
        command=guardar_imagenes, bg=color_interfaz("#1b1d20"), fg=paleta["texto"],
        selectcolor=color_interfaz("#29313d")).pack(anchor="w", padx=10, pady=8)
    bloque_diseño = tk.Frame(contenido, bg=color_interfaz("#1b1d20"), highlightbackground=color_interfaz("#2d3137"), highlightthickness=1)
    bloque_diseño.pack(fill="x", pady=(0, 10), padx=0)

    cabecera_diseño = tk.Label(
        bloque_diseño, text="Tema", font=("Sans", 8, "bold"),
        fg=color_interfaz("#d0d0d0"), bg=color_interfaz("#1b1d20"), anchor="w"
    )
    cabecera_diseño.pack(anchor="w", padx=10, pady=(8, 6))

    fila_temas = tk.Frame(bloque_diseño, bg=color_interfaz("#1b1d20"))
    fila_temas.pack(fill="x", padx=10, pady=(0, 8))

    nombres_temas = NOMBRES_TEMAS

    for indice, nombre_tema in enumerate(nombres_temas):
        color_base = PALETA_TEMAS[nombre_tema]["base"]
        seleccionado = (config.get("color") or config.get("tema") or "gris") == nombre_tema

        tarjeta_tema = tk.Frame(
            fila_temas, bg=color_interfaz("#232323"), cursor="hand2",
            highlightbackground=color_base if seleccionado else color_interfaz("#3a3d41"),
            highlightthickness=2 if seleccionado else 1
        )
        tarjeta_tema.grid(row=indice // 3, column=indice % 3, sticky="ew", padx=3, pady=3)
        fila_temas.grid_columnconfigure(indice % 3, weight=1)

        circulo = tk.Label(
            tarjeta_tema, text="●", font=("Sans", 16, "bold"),
            fg=color_base, bg=color_interfaz("#232323"),
            cursor="hand2",
            padx=4, pady=3
        )
        circulo.pack(anchor="center")
        etiqueta_tema = tk.Label(
            tarjeta_tema, text=nombres_temas[nombre_tema], font=("Sans", 7),
            fg=color_interfaz("#d0d0d0"), bg=color_interfaz("#232323"), cursor="hand2", wraplength=115
        )
        etiqueta_tema.pack(anchor="center", padx=3, pady=(0, 4))
        for widget in (tarjeta_tema, circulo, etiqueta_tema):
            widget.bind("<Button-1>", lambda event, n=nombre_tema: aplicar_tema(n))

    opciones_lectura = tk.Frame(bloque_diseño, bg=color_interfaz("#1b1d20"))
    opciones_lectura.pack(fill="x", padx=0, pady=(16, 10))
    opciones_lectura.grid_columnconfigure(0, weight=1)
    opciones_lectura.grid_columnconfigure(1, weight=1)

    mostrar_es = config.get("mostrar_titulo_es", True)
    opcion_titulo = tk.Frame(
        opciones_lectura, bg=color_interfaz("#232323"), cursor="hand2",
        highlightbackground=color_interfaz("#2d3137"), highlightthickness=1
    )
    opcion_titulo.grid(row=0, column=0, sticky="nsew", padx=(10, 4))

    texto_titulo = tk.Frame(opcion_titulo, bg=color_interfaz("#232323"), cursor="hand2")
    texto_titulo.pack(fill="x", padx=10, pady=(9, 4))
    tk.Label(
        texto_titulo, text="Título en español", font=("Sans", 8, "bold"),
        fg=color_interfaz("#e0e3e7"), bg=color_interfaz("#232323"), cursor="hand2"
    ).pack(anchor="w")
    tk.Label(
        texto_titulo, text="Muestra la traducción debajo del título original.", font=("Sans", 7),
        fg=color_interfaz("#89929d"), bg=color_interfaz("#232323"), cursor="hand2", wraplength=155
    ).pack(anchor="w", pady=(3, 0))

    estado_titulo = tk.Label(
        opcion_titulo, text="ACTIVADO" if mostrar_es else "DESACTIVADO",
        font=("Sans", 7, "bold"),
        fg=color_interfaz("#111315") if mostrar_es else color_interfaz("#9aa4b2"),
        bg=paleta["base"] if mostrar_es else color_interfaz("#343941"),
        cursor="hand2", padx=8, pady=4
    )
    estado_titulo.pack(anchor="e", padx=10, pady=(0, 9))

    def alternar_titulo_es(event=None):
        config["mostrar_titulo_es"] = not mostrar_titulo_traducido()
        guardar_config()
        refrescar_vista_debounced()

    for widget in (opcion_titulo, texto_titulo, estado_titulo, *texto_titulo.winfo_children()):
        widget.bind("<Button-1>", alternar_titulo_es)

    fila_columnas = tk.Frame(
        opciones_lectura, bg=color_interfaz("#232323"), highlightbackground=color_interfaz("#2d3137"), highlightthickness=1
    )
    fila_columnas.grid(row=0, column=1, sticky="nsew", padx=(4, 10))

    texto_columnas = tk.Frame(fila_columnas, bg=color_interfaz("#232323"))
    texto_columnas.pack(fill="x", padx=10, pady=(9, 4))
    tk.Label(
        texto_columnas, text="Artículos por fila", font=("Sans", 8, "bold"),
        fg=color_interfaz("#e0e3e7"), bg=color_interfaz("#232323")
    ).pack(anchor="w")
    tk.Label(
        texto_columnas, text="Define la cantidad de tarjetas visibles en cada fila.", font=("Sans", 7),
        fg=color_interfaz("#89929d"), bg=color_interfaz("#232323"), wraplength=155
    ).pack(anchor="w", pady=(3, 0))

    selector_columnas = tk.Frame(fila_columnas, bg=color_interfaz("#1a1c20"))
    selector_columnas.pack(anchor="e", padx=10, pady=(0, 9))
    columnas_actuales = int(config.get("articulos_por_fila", 4))
    for cantidad in (1, 2, 3, 4, 5):
        seleccionada = cantidad == columnas_actuales
        boton_columna = tk.Label(
            selector_columnas, text=str(cantidad), font=("Sans", 8, "bold"),
            fg=color_interfaz("#111315") if seleccionada else color_interfaz("#aeb7c2"),
            bg=paleta["base"] if seleccionada else color_interfaz("#1a1c20"),
            cursor="hand2", padx=7, pady=4
        )
        boton_columna.pack(side="left", padx=1, pady=1)
        boton_columna.bind(
            "<Button-1>",
            lambda event, valor=cantidad: (
                config.__setitem__("articulos_por_fila", valor),
                guardar_config(),
                refrescar_vista_debounced()
            )
        )

def vista_seccion_categorias():
    def boton_pequeno(padre, texto, comando):
        b = tk.Label(
            padre, text=texto, font=("Sans", 8, "bold"), fg=color_interfaz("#aaaaaa"),
            bg=color_interfaz("#2a2a2a"), cursor="hand2", padx=5
        )
        b.bind("<Button-1>", lambda event: comando())
        return b

    bloque_categorias = tk.Frame(contenido, bg=color_interfaz("#1b1d20"), highlightbackground=color_interfaz("#2d3137"), highlightthickness=1)
    bloque_categorias.pack(fill="x", pady=(0, 10), padx=0)

    cabecera = tk.Frame(bloque_categorias, bg=color_interfaz("#1b1d20"))
    cabecera.pack(fill="x", padx=10, pady=(10, 6))
    tk.Label(cabecera, text="Organiza tus fuentes", font=("Sans", 8), fg=color_interfaz("#8f99a5"), bg=color_interfaz("#1b1d20")).pack(side="left")
    agregar = tk.Label(
        cabecera, text="+  Añadir categoría", font=("Sans", 8, "bold"),
        fg=color_interfaz("#111315"), bg=paleta["base"], cursor="hand2", padx=10, pady=6
    )
    agregar.pack(side="right")
    agregar.bind("<Button-1>", lambda event: abrir_dialogo_agregar_categoria())

    tarjetas = []

    def iniciar_arrastre_categoria(event, indice):
        categoria_arrastre["indice"] = indice
        categoria_arrastre["movido"] = False

    def mover_categoria_con_mouse(event):
        if categoria_arrastre["indice"] is not None:
            categoria_arrastre["movido"] = True

    def soltar_categoria(event, categoria):
        indice_origen = categoria_arrastre["indice"]
        fue_arrastre = categoria_arrastre["movido"]
        categoria_arrastre["indice"] = None
        if indice_origen is None:
            return
        if fue_arrastre:
            indice_destino = min(
                range(len(tarjetas)),
                key=lambda i: abs(event.y_root - (tarjetas[i].winfo_rooty() + tarjetas[i].winfo_height() // 2))
            )
            if indice_destino != indice_origen:
                elemento = config["categorias"].pop(indice_origen)
                config["categorias"].insert(indice_destino, elemento)
                guardar_config()
                vista_admin()
            return
        nombre = categoria["nombre"]
        if nombre in categorias_admin_expandidas:
            categorias_admin_expandidas.remove(nombre)
        else:
            categorias_admin_expandidas.add(nombre)
        vista_admin()

    for indice_cat, categoria in enumerate(config["categorias"]):
        nombre_cat = categoria["nombre"]
        expandida = nombre_cat in categorias_admin_expandidas

        tarjeta = tk.Frame(bloque_categorias, bg=color_interfaz("#232323"), highlightbackground=paleta["base"] if expandida else color_interfaz("#30363e"), highlightthickness=2 if expandida else 1, cursor="hand2")
        tarjeta.pack(fill="x", pady=(4, 0), padx=10)
        tarjetas.append(tarjeta)

        cabecera_cat = tk.Frame(tarjeta, bg=color_interfaz("#232323"), cursor="hand2")
        cabecera_cat.pack(fill="x", padx=8, pady=8)
        indicador = tk.Label(cabecera_cat, text="⌄" if expandida else "›", font=("Sans", 12, "bold"), fg=paleta["base"] if expandida else color_interfaz("#89929d"), bg=color_interfaz("#232323"), cursor="hand2")
        indicador.pack(side="left")
        titulo = tk.Label(cabecera_cat, text=nombre_cat, font=("Sans", 9, "bold"), fg=color_interfaz("#e0e3e7"), bg=color_interfaz("#232323"), cursor="hand2")
        titulo.pack(side="left", padx=(8, 0))
        tk.Label(cabecera_cat, text=f"{len(categoria['sitios'])} fuentes", font=("Sans", 7), fg=color_interfaz("#89929d"), bg=color_interfaz("#232323"), cursor="hand2").pack(side="left", padx=8)
        boton_pequeno(cabecera_cat, "Editar", lambda c=categoria: abrir_dialogo_editar_categoria(c)).pack(side="right", padx=2)
        boton_pequeno(cabecera_cat, "✕", lambda i=indice_cat: borrar_categoria(i)).pack(side="right", padx=2)

        for widget in (tarjeta, cabecera_cat, indicador, titulo):
            widget.bind("<ButtonPress-1>", lambda event, i=indice_cat: iniciar_arrastre_categoria(event, i))
            widget.bind("<B1-Motion>", mover_categoria_con_mouse)
            widget.bind("<ButtonRelease-1>", lambda event, c=categoria: soltar_categoria(event, c))

        if expandida:
            detalle = tk.Frame(tarjeta, bg=color_interfaz("#1b1d20"))
            detalle.pack(fill="x", padx=8, pady=(0, 8))
            for sitio_actual in categoria["sitios"]:
                fila = tk.Frame(detalle, bg=color_interfaz("#1a1c20"), highlightbackground=color_interfaz("#30363e"), highlightthickness=1)
                fila.pack(fill="x", pady=2)
                favicon = obtener_imagen_favicon(sitio_actual)
                if favicon is not None:
                    icono = tk.Label(fila, image=favicon, bg=color_interfaz("#1a1c20"))
                    icono.image = favicon
                    icono.pack(side="left", padx=(8, 0))
                else:
                    tk.Label(fila, text="", bg=color_interfaz("#59616b"), width=1, height=1).pack(side="left", padx=(8, 0))
                tk.Label(fila, text=sitio_actual["nombre"], font=("Sans", 8, "bold"), fg=color_interfaz("#d4d9de"), bg=color_interfaz("#1a1c20")).pack(side="left", padx=8, pady=7)
                otras_categorias = categorias_duplicadas_de_fuente(sitio_actual["url"], nombre_cat)
                if otras_categorias:
                    tk.Label(
                        fila, text="También en: " + ", ".join(otras_categorias), font=("Sans", 7),
                        fg=paleta["base_fuerte"], bg=color_interfaz("#1a1c20")
                    ).pack(side="left", padx=(0, 8))
                tk.Label(fila, text=sitio_actual.get("url_feed") or sitio_actual["url"], font=("Sans", 7), fg=color_interfaz("#89929d"), bg=color_interfaz("#1a1c20"), anchor="w").pack(side="left", fill="x", expand=True, padx=(2, 8))
                boton_pequeno(fila, "Editar", lambda s=sitio_actual: abrir_dialogo_editar_fuente(s)).pack(side="right", padx=5)
            agregar_fuente = tk.Label(detalle, text="+ Añadir fuente a esta categoría", font=("Sans", 8, "bold"), fg=paleta["base_fuerte"], bg=color_interfaz("#1b1d20"), cursor="hand2", padx=6, pady=7)
            agregar_fuente.pack(anchor="center", pady=(4, 0))
            agregar_fuente.bind("<Button-1>", lambda event, n=nombre_cat: abrir_dialogo_agregar_fuente(n))

    tk.Frame(bloque_categorias, bg=color_interfaz("#1b1d20"), height=8).pack(fill="x")

def vista_seccion_fuentes():
    nombres_cat = nombres_categorias()

    def boton_pequeno(padre, texto, comando):
        b = tk.Label(
            padre, text=texto, font=("Sans", 8, "bold"), fg=color_interfaz("#aaaaaa"),
            bg=color_interfaz("#2a2a2a"), cursor="hand2", padx=5
        )
        b.bind("<Button-1>", lambda event: comando())
        return b

    bloque_fuentes = tk.Frame(contenido, bg=color_interfaz("#1b1d20"), highlightbackground=color_interfaz("#2d3137"), highlightthickness=1)
    bloque_fuentes.pack(fill="x", pady=(0, 10), padx=0)

    cabecera = tk.Frame(bloque_fuentes, bg=color_interfaz("#1b1d20"))
    cabecera.pack(fill="x", padx=10, pady=(10, 6))
    tk.Label(cabecera, text="Gestiona tus sitios y feeds", font=("Sans", 8), fg=color_interfaz("#8f99a5"), bg=color_interfaz("#1b1d20")).pack(side="left")
    agregar = tk.Label(cabecera, text="+", font=("Sans", 13, "bold"), fg=color_interfaz("#111315"), bg=paleta["base"], cursor="hand2", width=2, pady=1)
    agregar.pack(side="right")
    agregar.bind("<Button-1>", lambda event: abrir_dialogo_agregar_fuente())

    for categoria in config["categorias"]:
        nombre_cat = categoria["nombre"]

        tk.Label(
            bloque_fuentes,
            text=f"{nombre_cat}",
            font=("Sans", 7, "bold"),
            fg=color_interfaz("#b6bcc5"),
            bg=color_interfaz("#1b1d20")
        ).pack(anchor="w", padx=10, pady=(8, 2))

        for indice_sitio, sitio_actual in enumerate(categoria["sitios"]):
            url_clave = sitio_actual["url"]

            fila_sitio = tk.Frame(bloque_fuentes, bg=color_interfaz("#232323"), highlightbackground=color_interfaz("#30363e"), highlightthickness=1)
            fila_sitio.pack(fill="x", padx=10, pady=2)

            sin_feed = datos_articulos.get(url_clave) is None
            icono_admin = obtener_imagen_favicon(sitio_actual)

            if icono_admin is not None:
                tk.Label(fila_sitio, image=icono_admin, bg=color_interfaz("#232323")).pack(side="left", padx=(6, 2))

            tk.Label(
                fila_sitio, text="   " + sitio_actual["nombre"], font=("Sans", 8),
                fg=color_interfaz("#c97a7a") if sin_feed else color_interfaz("#d4d9de"), bg=color_interfaz("#232323"), anchor="w"
            ).pack(side="left", fill="x", expand=True)

            var_categoria = tk.StringVar(value=nombre_cat)
            menu_categoria = tk.OptionMenu(
                fila_sitio, var_categoria, *nombres_cat,
                command=lambda nueva, nc=nombre_cat, i=indice_sitio: mover_sitio_a_categoria(nc, i, nueva)
            )
            menu_categoria.config(bg=color_interfaz("#2a2a2a"), fg=color_interfaz("#d0d0d0"), highlightthickness=0, font=("Sans", 7), bd=0)
            menu_categoria["menu"].config(bg=color_interfaz("#2a2a2a"), fg=color_interfaz("#d0d0d0"), font=("Sans", 7))
            menu_categoria.pack(side="left", padx=4)

            boton_pequeno(fila_sitio, "✎", lambda u=url_clave: empezar_a_editar(u)).pack(side="left", padx=1)
            boton_pequeno(fila_sitio, "↑", lambda nc=nombre_cat, i=indice_sitio: mover_sitio(nc, i, -1)).pack(side="left", padx=1)
            boton_pequeno(fila_sitio, "↓", lambda nc=nombre_cat, i=indice_sitio: mover_sitio(nc, i, 1)).pack(side="left", padx=1)
            boton_pequeno(fila_sitio, "✕", lambda nc=nombre_cat, i=indice_sitio: borrar_sitio(nc, i)).pack(side="left", padx=1)

            if url_en_edicion == url_clave:
                panel_editar = tk.Frame(bloque_fuentes, bg=color_interfaz("#232323"))
                panel_editar.pack(fill="x", pady=(0, 6), padx=(20, 10))

                fila_link = tk.Frame(panel_editar, bg=color_interfaz("#232323"))
                fila_link.pack(fill="x", padx=6, pady=(6, 3))
                tk.Label(fila_link, text="Link:", font=("Sans", 7), fg=color_interfaz("#888888"), bg=color_interfaz("#232323"), width=16, anchor="w").pack(side="left")
                entrada_editar_link = tk.Entry(fila_link, bg=color_interfaz("#2a2a2a"), fg=color_interfaz("#d0d0d0"), insertbackground=color_interfaz("#d0d0d0"), relief="flat", font=("Sans", 7))
                entrada_editar_link.insert(0, sitio_actual.get("url_feed") or sitio_actual["url"])
                entrada_editar_link.pack(side="left", fill="x", expand=True, ipady=2)
                entrada_editar_link.bind("<Button-1>", lambda event, w=entrada_editar_link: forzar_foco(w))

                fila_max = tk.Frame(panel_editar, bg=color_interfaz("#232323"))
                fila_max.pack(fill="x", padx=6, pady=3)
                tk.Label(fila_max, text="Artículos a mostrar:", font=("Sans", 7), fg=color_interfaz("#888888"), bg=color_interfaz("#232323"), width=16, anchor="w").pack(side="left")
                entrada_editar_max = tk.Entry(fila_max, bg=color_interfaz("#2a2a2a"), fg=color_interfaz("#d0d0d0"), insertbackground=color_interfaz("#d0d0d0"), relief="flat", font=("Sans", 7), width=6)
                entrada_editar_max.insert(0, str(sitio_actual.get("max_articulos") or ARTICULOS_POR_SITIO))
                entrada_editar_max.pack(side="left", ipady=2)
                entrada_editar_max.bind("<Button-1>", lambda event, w=entrada_editar_max: forzar_foco(w))

                fila_intervalo = tk.Frame(panel_editar, bg=color_interfaz("#232323"))
                fila_intervalo.pack(fill="x", padx=6, pady=3)
                tk.Label(fila_intervalo, text="Actualizar cada (min):", font=("Sans", 7), fg=color_interfaz("#888888"), bg=color_interfaz("#232323"), width=16, anchor="w").pack(side="left")
                entrada_editar_intervalo = tk.Entry(fila_intervalo, bg=color_interfaz("#2a2a2a"), fg=color_interfaz("#d0d0d0"), insertbackground=color_interfaz("#d0d0d0"), relief="flat", font=("Sans", 7), width=6)
                entrada_editar_intervalo.insert(0, str(sitio_actual.get("intervalo_min") or MINUTOS_ENTRE_ACTUALIZACIONES))
                entrada_editar_intervalo.pack(side="left", ipady=2)
                entrada_editar_intervalo.bind("<Button-1>", lambda event, w=entrada_editar_intervalo: forzar_foco(w))

                fila_idioma = tk.Frame(panel_editar, bg=color_interfaz("#232323"))
                fila_idioma.pack(fill="x", padx=6, pady=3)
                tk.Label(fila_idioma, text="Títulos:", font=("Sans", 7), fg=color_interfaz("#888888"), bg=color_interfaz("#232323"), width=16, anchor="w").pack(side="left")
                var_modo_titulo = tk.StringVar(value=sitio_actual.get("modo_titulo", "en_es"))
                menu_idioma = tk.OptionMenu(fila_idioma, var_modo_titulo, "solo_ingles", "en_es")
                menu_idioma.config(bg=color_interfaz("#2a2a2a"), fg=color_interfaz("#d0d0d0"), highlightthickness=0, font=("Sans", 7), bd=0)
                menu_idioma["menu"].config(bg=color_interfaz("#2a2a2a"), fg=color_interfaz("#d0d0d0"), font=("Sans", 7))
                menu_idioma.pack(side="left")

                var_trad_es = tk.BooleanVar(value=bool(sitio_actual.get("traduccion_es", True)))
                check_es = tk.Checkbutton(
                    fila_idioma, text="🇪🇸 Español", variable=var_trad_es,
                    font=("Sans", 7), fg=color_interfaz("#aaaaaa"), bg=color_interfaz("#232323"),
                    activebackground=color_interfaz("#232323"), activeforeground=color_interfaz("#aaaaaa"),
                    selectcolor=color_interfaz("#3a3a3a"), highlightthickness=0, bd=0,
                    indicatoron=True, tristatevalue=0,
                    state="normal" if var_modo_titulo.get() == "en_es" else "disabled"
                )
                check_es.pack(side="left", padx=(8, 0))
                var_modo_titulo.trace_add("write", lambda *args, w=check_es: w.configure(state="normal" if var_modo_titulo.get() == "en_es" else "disabled"))

                fila_imagen = tk.Frame(panel_editar, bg=color_interfaz("#232323"))
                fila_imagen.pack(fill="x", padx=6, pady=3)
                var_editar_imagen = tk.BooleanVar(value=sitio_actual.get("mostrar_imagen", False))
                check_imagen = tk.Checkbutton(
                    fila_imagen, text="Mostrar miniatura de imagen", variable=var_editar_imagen,
                    font=("Sans", 7), fg=color_interfaz("#aaaaaa"), bg=color_interfaz("#232323"),
                    activebackground=color_interfaz("#232323"), activeforeground=color_interfaz("#aaaaaa"),
                    selectcolor=color_interfaz("#3a3a3a"), highlightthickness=0, bd=0,
                    indicatoron=True, tristatevalue=0
                )
                check_imagen.bind("<Enter>", lambda event, w=check_imagen: w.configure(selectcolor=paleta["base"], activebackground=color_interfaz("#232323")))
                check_imagen.bind("<Leave>", lambda event, w=check_imagen: w.configure(selectcolor=color_interfaz("#3a3a3a"), activebackground=color_interfaz("#232323")))
                check_imagen.pack(side="left")

                fila_favicon = tk.Frame(panel_editar, bg=color_interfaz("#232323"))
                fila_favicon.pack(fill="x", padx=6, pady=3)
                tk.Label(fila_favicon, text="Favicon:", font=("Sans", 7), fg=color_interfaz("#888888"), bg=color_interfaz("#232323"), width=16, anchor="w").pack(side="left")
                estado_favicon = "Personalizado" if sitio_actual.get("favicon_personalizado") and os.path.isfile(sitio_actual.get("favicon_personalizado")) else "Automático"
                tk.Label(fila_favicon, text=estado_favicon, font=("Sans", 7), fg=color_interfaz("#aaaaaa"), bg=color_interfaz("#232323")).pack(side="left", padx=(0, 6))
                boton_pequeno(fila_favicon, "Subir imagen", lambda s=sitio_actual: seleccionar_favicon_personalizado(s)).pack(side="left", padx=(0, 4))
                if sitio_actual.get("favicon_personalizado"):
                    boton_pequeno(fila_favicon, "Usar automático", lambda s=sitio_actual: quitar_favicon_personalizado(s)).pack(side="left")

                fila_botones_editar = tk.Frame(panel_editar, bg=color_interfaz("#232323"))
                fila_botones_editar.pack(fill="x", padx=6, pady=(3, 6))
                boton_pequeno(
                    fila_botones_editar, "Guardar",
                    lambda s=sitio_actual, el=entrada_editar_link, em=entrada_editar_max,
                           ei=entrada_editar_intervalo, vi=var_editar_imagen,
                           vm=var_modo_titulo, ve=var_trad_es:
                        guardar_edicion(s, el, em, ei, vi, vm, ve)
                ).pack(side="left", padx=(0, 4))
                boton_pequeno(fila_botones_editar, "Cancelar", cancelar_edicion).pack(side="left")

                if not PIL_DISPONIBLE:
                    tk.Label(panel_editar, text="Nota: instala Pillow (sudo apt install python3-pil python3-pil.imagetk) para que las miniaturas funcionen con imágenes JPG.", font=("Sans", 6), fg=color_interfaz("#666666"), bg=color_interfaz("#232323"), wraplength=ancho_actual - 80, justify="left").pack(anchor="w", padx=6, pady=(0, 6))

mensaje_admin = None

url_en_edicion = None  # url del sitio (clave) cuyo link se está editando

categorias_admin_expandidas = set()
categoria_arrastre = {"indice": None, "movido": False}


def empezar_a_editar(url_sitio):

    global url_en_edicion

    url_en_edicion = url_sitio
    vista_admin()


def empezar_a_editar_desde_categoria(url_sitio):
    global url_en_edicion, seccion_config, modo_admin
    url_en_edicion = url_sitio
    modo_admin = True
    seccion_config = "fuentes"
    actualizar_estado_botones_inferiores()
    vista_admin()


def cancelar_edicion():

    global url_en_edicion

    url_en_edicion = None
    vista_admin()


def guardar_edicion(sitio_actual, entrada_link, entrada_max, entrada_intervalo, var_imagen, var_modo_titulo=None, var_trad_es=None):

    nuevo_link = entrada_link.get().strip()

    recargar = False

    if nuevo_link:

        if not nuevo_link.startswith("http"):
            nuevo_link = "https://" + nuevo_link

        if nuevo_link != (sitio_actual.get("url_feed") or ""):
            sitio_actual["url_feed"] = nuevo_link
            recargar = True

    texto_max = entrada_max.get().strip()

    if texto_max.isdigit() and int(texto_max) != (sitio_actual.get("max_articulos") or ARTICULOS_POR_SITIO):
        sitio_actual["max_articulos"] = int(texto_max)
        recargar = True

    texto_intervalo = entrada_intervalo.get().strip()

    if texto_intervalo.isdigit():
        sitio_actual["intervalo_min"] = int(texto_intervalo)

    if var_modo_titulo is not None:
        modo = var_modo_titulo.get()
        sitio_actual["modo_titulo"] = modo if modo in {"solo_ingles", "en_es"} else "en_es"

    if var_trad_es is not None:
        sitio_actual["traduccion_es"] = bool(var_trad_es.get())

    mostrar_imagen_antes = sitio_actual.get("mostrar_imagen", False)
    mostrar_imagen_ahora = var_imagen.get()

    sitio_actual["mostrar_imagen"] = mostrar_imagen_ahora

    if mostrar_imagen_ahora != mostrar_imagen_antes:
        recargar = True

    if sitio_actual.get("modo_titulo") == "solo_ingles":
        sitio_actual["traduccion_es"] = False

    guardar_config()

    cancelar_edicion()

    if recargar:

        refrescar_vista()
        pie_estado.config(text="Cambios guardados · Pulsa Actualizar feed")


# ============================================================
# INICIO
# ============================================================

tk.Button(contenedor_botones, text="Radar", command=ir_a_radar, anchor="w",
          bg=color_interfaz("#191d23"), fg=paleta["texto"], relief="flat", bd=0,
          padx=12, pady=10, font=("Sans", 8)).pack(fill="x")
busqueda_var = tk.StringVar()
panel_busqueda = tk.Frame(area_lectura, bg=color_interfaz("#111315"))
panel_busqueda.pack(fill="x", before=area_desplazable, padx=14, pady=(10, 0))
marco_busqueda, buscador_principal = crear_buscador(panel_busqueda, busqueda_var, "Buscar en títulos")
marco_busqueda.pack(fill="x")
busqueda_pendiente = None
def cambiar_busqueda(*args):
    global busqueda_titulos, busqueda_pendiente
    busqueda_titulos = busqueda_var.get().strip()
    if busqueda_pendiente:
        ventana.after_cancel(busqueda_pendiente)
    def aplicar_busqueda():
        global busqueda_pendiente
        busqueda_pendiente = None
        refrescar_vista()
    busqueda_pendiente = ventana.after(200, aplicar_busqueda)
busqueda_var.trace_add("write", cambiar_busqueda)


for categoria in config["categorias"]:
    for sitio_actual in categoria["sitios"]:
        datos_articulos[sitio_actual["url"]] = "cargando"

cargar_iconos_botones()
actualizar_estado_botones_inferiores()
# Un solo rastreador para toda la ventana evita los Enter/Leave encadenados
# entre los widgets internos de una tarjeta. Solo cambia el color del borde.
ventana.bind_all("<Motion>", actualizar_hover_tarjeta, add="+")
vista_lectura()

actualizar_todo_manual()


posicionar_abajo_izquierda()

ventana.bind("<Escape>", lambda event: ventana.destroy())

ventana.mainloop()
