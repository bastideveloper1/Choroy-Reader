"""Motor Python de Choroy Reader. Sin dependencias de Tkinter ni de Qt."""
import io
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


class HtmlContent(HTMLParser):
    """Extrae texto legible y metadatos sin ejecutar código de la página."""
    def __init__(self):
        super().__init__()
        self.parts = []
        self.image = None
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag in {"script", "style", "noscript"}:
            self.skip_depth += 1
        if tag in {"p", "div", "br", "h1", "h2", "h3", "li", "blockquote"}:
            self.parts.append("\n\n")
        if tag == "meta" and (attributes.get("property") or attributes.get("name")) in {"og:image", "twitter:image"}:
            self.image = attributes.get("content") or self.image
        if tag == "img":
            self.image = self.image or attributes.get("src") or attributes.get("data-src")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"}:
            self.skip_depth = max(0, self.skip_depth - 1)
        if tag in {"p", "div", "h1", "h2", "h3", "li", "blockquote"}:
            self.parts.append("\n\n")

    def handle_data(self, data):
        if not self.skip_depth:
            self.parts.append(data)

    def text(self):
        return "\n\n".join(
            re.sub(r"\s+", " ", block).strip()
            for block in "".join(self.parts).split("\n\n") if block.strip()
        )

feed_content = {}

def save_feed_content(link, element):
    blocks = []
    for child in element:
        if child.tag.split("}")[-1] in {"encoded", "content", "description", "summary"}:
            blocks.append("".join(child.itertext()))
    html = max(blocks, key=len, default="")
    if html:
        feed_content[link] = html
    parser = HtmlContent()
    parser.feed(html)
    return parser.image

def article_text(html):
    # BeautifulSoup permite acotar el texto al cuerpo editorial.
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        for node in soup.select("script, style, noscript, nav, header, footer, aside, form"):
            node.decompose()
        body = soup.select_one('[itemprop="articleBody"]') or soup.find("article") or soup.find("main")
        if body is None:
            return ""
        blocks = [n.get_text(" ", strip=True) for n in body.select("p, h2, h3, li, blockquote")]
        return "\n\n".join(b for b in blocks if b)
    except ImportError:
        return ""

ARTICLES_PER_SOURCE = 3


THEME_PALETTE = {
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

THEME_NAMES = {
    "periodico": "Claro periódico",
    "gris": "Gris minimalista",
    "morado_neon": "Lila eléctrico",
    "azul_neon": "Azul ártico",
    "amarillo_neon": "Amarillo solar",
    "verde_neon": "Verde menta",
    "rosa_neon": "Rosa cerezo japonés",
}

THEME_PALETTE["periodico"] = {
    "base": "#454545", "base_fuerte": "#202020", "hover": "#000000",
    "cerrar": "#555555", "cerrar_hover": "#000000",
    "card_bg": "#e6e6e6", "card_hover": "#d8d8d8", "card_borde": "#b5b3ad",
    "texto": "#171717", "texto_sec": "#565656", "link": "#202020", "link_hover": "#000000",
}

def source_defaults(name, url):
    return {
        "nombre": name,
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

DEFAULT_CONFIG = {
    "tema": "gris",
    "color": "gris",
    "mostrar_titulo_es": True,
    "articulos_por_fila": 5,
    "categorias": [
        {
            "nombre": "Newspapers: Cybersecurity",
            "sitios": [
                source_defaults("The Record", "https://therecord.media/"),
                source_defaults("Cybernews", "https://cybernews.com/"),
                source_defaults("Dark Reading", "https://www.darkreading.com"),
                source_defaults("The Hacker News", "https://thehackernews.com/"),
                source_defaults("BleepingComputer", "https://www.bleepingcomputer.com/"),
                source_defaults("KrebsOnSecurity", "https://krebsonsecurity.com/"),
            ],
        },
        {
            "nombre": "Newspapers",
            "sitios": [
                source_defaults("MIT Technology Review", "https://www.technologyreview.com/"),
                source_defaults("Ethic", "https://ethic.es/"),
                source_defaults("Futuro.cl", "https://www.futuro.cl/"),
            ],
        },
        {
            "nombre": "Blogs",
            "sitios": [
                source_defaults("Schneier on Security", "https://www.schneier.com/"),
                source_defaults("elhacker.net", "https://elhacker.net/"),
            ],
        },
        {
            "nombre": "Privacidad y herramientas",
            "sitios": [
                source_defaults("PrivacyTools", "https://privacytools.io/es"),
                source_defaults("EFF", "https://www.eff.org/"),
                source_defaults("Privacy Guides", "https://www.privacyguides.org/posts/tag/articles/"),
                source_defaults("Matrix.org", "https://matrix.org/"),
                source_defaults("EDRi", "https://edri.org/"),
                source_defaults("The New Oil", "https://thenewoil.org/en/"),
                source_defaults("Tuta", "https://tuta.com/es/blog"),
                source_defaults("Cryptomator", "https://cryptomator.org/blog/"),
                source_defaults("Proton", "https://proton.me/es-419/blog"),
                source_defaults("Signal", "https://signal.org/blog/"),
                source_defaults("Ente", "https://ente.com/blog/"),
                source_defaults("Tor Project", "https://blog.torproject.org/"),
                source_defaults("Mastodon", "https://blog.joinmastodon.org/"),
                source_defaults("SimpleLogin", "https://simplelogin.io/blog/"),
                source_defaults("Quad9", "https://quad9.net/es/news/blog/"),
                source_defaults("Mullvad", "https://mullvad.net/es/blog"),
                source_defaults("Mozilla", "https://blog.mozilla.org/en/"),
                source_defaults("Bitwarden", "https://bitwarden.com/blog/"),
                source_defaults("Keep Android Open", "https://keepandroidopen.org/es/"),
                source_defaults("Fastmail", "https://www.fastmail.com/blog/"),
                source_defaults("Yubico", "https://www.yubico.com/blog/?lang=es"),
                source_defaults("Have I Been Pwned", "https://haveibeenpwned.com/"),
            ],
        },
    ],
    "vistos": [],
}

def download(url, timeout=10):

    request = urllib.request.Request(
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

    with urllib.request.urlopen(request, timeout=timeout) as response:

        data = response.read()

        if response.info().get("Content-Encoding") == "gzip":
            data = gzip.decompress(data)

        return data

NS_MEDIA = "{http://search.yahoo.com/mrss/}"

NS_ATOM = "{http://www.w3.org/2005/Atom}"

def extract_rss_image(item_el):

    enclosure = item_el.find("enclosure")

    if enclosure is not None and enclosure.get("url"):
        kind = (enclosure.get("type") or "").lower()
        url = enclosure.get("url")
        if "image" in kind or re.search(r"\.(jpg|jpeg|png|webp|gif)(?:[?#].*)?$", url, re.IGNORECASE):
            return url

    thumb = item_el.find(NS_MEDIA + "thumbnail")

    if thumb is not None and thumb.get("url"):
        return thumb.get("url")

    media_content = item_el.find(NS_MEDIA + "content")

    if media_content is not None and media_content.get("url"):
        kind = (media_content.get("type") or "").lower()
        url = media_content.get("url")
        if "image" in kind or re.search(r"\.(jpg|jpeg|png|webp|gif)(?:[?#].*)?$", url, re.IGNORECASE):
            return url

    desc_el = item_el.find("description")

    if desc_el is not None and desc_el.text:

        match = re.search(r'<img[^>]+(?:src|data-src)=["\']([^"\']+)["\']', desc_el.text, re.IGNORECASE)

        if match:
            return match.group(1)

    return None

def extract_atom_image(entry_element):

    for link_el in entry_element.findall(NS_ATOM + "link"):

        if link_el.get("rel") == "enclosure" and "image" in (link_el.get("type") or ""):
            return link_el.get("href")

    thumb = entry_element.find(NS_MEDIA + "thumbnail")

    if thumb is not None and thumb.get("url"):
        return thumb.get("url")

    return None

def parse_feed(data, maximum=ARTICLES_PER_SOURCE):

    root = ET.fromstring(data)

    items = root.findall(".//item")

    if items:

        articles = []

        for item in items[:maximum]:

            title_element = item.find("title")
            link_el = item.find("link")
            date_element = item.find("pubDate")
            if date_element is None:
                date_element = item.find("{http://purl.org/dc/elements/1.1/}date")

            title = (
                title_element.text.strip()
                if title_element is not None and title_element.text
                else "(sin título)"
            )

            link = (
                link_el.text.strip()
                if link_el is not None and link_el.text
                else ""
            )

            date = date_element.text.strip() if date_element is not None and date_element.text else ""
            content_image = save_feed_content(link, item)
            articles.append((title, link, extract_rss_image(item) or content_image, date))

        return articles

    ns = {"atom": "http://www.w3.org/2005/Atom"}

    entries = root.findall(".//atom:entry", ns)

    articles = []

    for entry in entries[:maximum]:

        title_element = entry.find("atom:title", ns)
        link_el = entry.find("atom:link", ns)
        date_element = entry.find("atom:published", ns)
        if date_element is None:
            date_element = entry.find("atom:updated", ns)

        title = (
            title_element.text.strip()
            if title_element is not None and title_element.text
            else "(sin título)"
        )

        link = link_el.get("href") if link_el is not None else ""
        date = date_element.text.strip() if date_element is not None and date_element.text else ""
        content_image = save_feed_content(link, entry)
        articles.append((title, link, extract_atom_image(entry) or content_image, date))

    return articles

def get_articles(feed_url, quiet=False, maximum=ARTICLES_PER_SOURCE):

    try:

        data = download(feed_url)

        return parse_feed(data, maximum=maximum)

    except Exception as e:

        if not quiet:
            print(f"[choroy_reader] Error cargando {feed_url}: {e}")

        return None

def get_open_graph_image(link):

    if not link:
        return None

    try:

        html = download(link, timeout=8).decode("utf-8", errors="ignore")

        parser = HtmlContent()
        parser.feed(html)
        if parser.image:
            return urllib.parse.urljoin(link, unescape(parser.image))

    except Exception:
        pass

    return None

def extract_feed_link(html, base_url):

    tags = re.findall(r"<link\b[^>]*>", html, re.IGNORECASE)

    for tag_name in tags:

        type_match = re.search(r'type=["\']([^"\']+)["\']', tag_name, re.IGNORECASE)
        href_m = re.search(r'href=["\']([^"\']+)["\']', tag_name, re.IGNORECASE)

        if not type_match or not href_m:
            continue

        kind = type_match.group(1).lower()

        if "rss+xml" in kind or "atom+xml" in kind:
            return urllib.parse.urljoin(base_url, href_m.group(1))

    return None

COMMON_FEED_PATHS = [
    "feed/", "feed", "rss/", "rss", "rss.xml", "atom.xml",
    "index.xml", ".rss", "feeds/posts/default", "blog/feed/",
    "blog/rss/", "blog/rss.xml", "en/feed/",
]

def discover_feed(site_url):

    try:

        html = download(site_url).decode("utf-8", errors="ignore")

        candidate = extract_feed_link(html, site_url)

        if candidate and get_articles(candidate, quiet=True) is not None:
            return candidate

    except Exception as e:

        print(f"[choroy_reader] No se pudo leer la portada de {site_url}: {e}")

    for suffix in COMMON_FEED_PATHS:

        candidate = urllib.parse.urljoin(site_url, suffix)

        if get_articles(candidate, quiet=True) is not None:
            return candidate

    print(f"[choroy_reader] No se encontró ningún feed para {site_url}")

    return None

def translate_text(text, target_language="es", skip_spanish=False):

    try:

        parameters = urllib.parse.urlencode({
            "client": "gtx",
            "sl": "auto",
            "tl": target_language,
            "dt": "t",
            "q": text
        })

        url = "https://translate.googleapis.com/translate_a/single?" + parameters

        request = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0"}
        )

        with urllib.request.urlopen(request, timeout=6) as response:
            data = json.loads(response.read().decode("utf-8"))

        if skip_spanish and len(data) > 2 and str(data[2]).lower().split("-")[0] == "es":
            return ""
        return "".join(excerpt[0] for excerpt in data[0])

    except Exception:

        return None

def parse_date(value):
    if not value:
        return None

    value = str(value).strip()
    if not value:
        return None

    try:
        return parsedate_to_datetime(value)
    except Exception:
        pass

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        pass

    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except Exception:
        pass

    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except Exception:
        pass

    return None

def relative_date(date):
    """Presenta una fecha del feed de manera breve y legible."""
    if date is None:
        return ""
    try:
        now = datetime.now(date.tzinfo) if date.tzinfo else datetime.now()
        seconds = max(0, int((now - date).total_seconds()))
    except Exception:
        return ""

    if seconds < 60:
        return "Ahora"
    if seconds < 3600:
        return f"Hace {seconds // 60} min"
    if seconds < 86400:
        return f"Hace {seconds // 3600} h"
    if seconds < 172800:
        return "Ayer"
    if seconds < 604800:
        return f"Hace {seconds // 86400} días"
    return date.strftime("%d %b %Y")

def create_quote_image(excerpt, source, link, translated=False, title="", color="#b9a0ff", image_bytes=None, original_language="", theme="gris") :
    """Genera una cita cuadrada con texto ajustado y atribución."""
    light = theme == "periodico"
    image = Image.new("RGB", (1080, 1080), "#e6e6e6" if light else "#171b20")
    drawing = ImageDraw.Draw(image)
    path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    def font_size(size):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            return ImageFont.load_default()
    def wrap_text(text, font, width):
        lines, line = [], ""
        for word in text.split():
            proposal = (line + " " + word).strip()
            if line and drawing.textlength(proposal, font=font) > width:
                lines.append(line)
                line = word
            else:
                line = proposal
        if line:
            lines.append(line)
        return lines
    try:
        title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 30)
    except OSError:
        title_font = font_size(30)
    title_lines = wrap_text(title, title_font, 880)
    title_divider = 205 + len(title_lines) * 40 + 16
    quote_y = title_divider + 44
    if image_bytes:
        with Image.open(io.BytesIO(image_bytes)) as cover:
            image.paste(ImageOps.fit(cover.convert("RGB"), (880, 240)), (94, quote_y))
        quote_y += 266
    spacing = max(200, 885 - quote_y)
    for size in range(48, 15, -2):
        font = font_size(size)
        lines = wrap_text(excerpt, font, 880)
        if len(lines) * (size + 14) <= spacing and all(drawing.textlength(l, font=font) <= 880 for l in lines):
            break
    drawing.rounded_rectangle((48, 48, 1032, 1032), radius=28, outline="#394453", width=2)
    drawing.rectangle((94, 108, 150, 114), fill=color)
    drawing.text((94, 145), "CITA EXTRAÍDA DEL ARTÍCULO", font=font_size(20), fill=color)
    drawing.multiline_text((94, 205), "\n".join(title_lines), font=title_font, fill=color, spacing=10)
    drawing.line((94, title_divider, 986, title_divider), fill="#adadad" if light else "#515b6a", width=2)
    drawing.multiline_text((94, quote_y), "\n".join(lines), font=font, fill="#202020" if light else "#edf1f7", spacing=14)
    drawing.line((94, 920, 986, 920), fill="#394453", width=2)
    language = {"en": "inglés", "es": "español"}.get(original_language)
    origin = "Versión original en " + language if language else "Versión original"
    attribution = source[:45] + " · " + origin
    drawing.text((94, 944), attribution, font=font_size(18), fill="#202020" if light else "#dbe1e9")
    drawing.text((94, 978), urllib.parse.urlparse(link).netloc[:75], font=font_size(17), fill="#8793a3")
    image.info["articulo"] = link
    return image
