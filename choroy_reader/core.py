"""Motor Python de Choroy Reader. Sin dependencias de Tkinter ni de Qt."""
import io
import re
import json
import time
import textwrap
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from html import unescape
from html.parser import HTMLParser
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageColor


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

def article_images(html, link, text):
    """Locate editorial images against the stable plain-text paragraphs."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    for node in soup.select('script, style, noscript, nav, header, footer, aside, form'):
        node.decompose()
    body = soup.select_one('[itemprop="articleBody"]') or soup.find('article') or soup.find('main') or soup
    paragraphs = text.split('\n\n')
    result, seen, paragraph = [], set(), 0
    for node in body.find_all(['p', 'h2', 'h3', 'li', 'blockquote', 'img']):
        if node.name != 'img':
            value = node.get_text(' ', strip=True)
            if value in paragraphs[paragraph:]:
                paragraph = paragraphs.index(value, paragraph)
            continue
        srcset = node.get('data-srcset') or node.get('srcset', '')
        responsive = srcset.split(',')[-1].strip().split(' ')[0]
        src = node.get('data-src') or node.get('data-original') or responsive or node.get('src')
        url = urllib.parse.urljoin(link, src or '')
        if urllib.parse.urlparse(url).scheme not in {'http', 'https'} or url in seen:
            continue
        if node.get('width') == '1' or node.get('height') == '1':
            continue
        seen.add(url)
        result.append(dict(url=url, paragraph=paragraph, alt=node.get('alt', '')))
    return result

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

from .network import download

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

QUOTE_BACKGROUNDS = [
    dict(key="choroy", name="Choroy · Verde y rojo", start="#078A5B", end="#A41632", light=False),
    dict(key="marfil", name="Marfil", start="#fff7e8", end="#fff7e8", light=True),
    dict(key="salvia", name="Salvia", start="#e0ecdf", end="#e0ecdf", light=True),
    dict(key="lavanda", name="Lavanda", start="#eee5f6", end="#eee5f6", light=True),
    dict(key="arena", name="Arena", start="#ead9be", end="#ead9be", light=True),
    dict(key="oceano", name="Océano", start="#102c46", end="#102c46", light=False),
    dict(key="bosque", name="Bosque", start="#163b31", end="#163b31", light=False),
    dict(key="vino", name="Vino", start="#421e35", end="#421e35", light=False),
    dict(key="grad_aurora", name="Degradado · Aurora", start="#24254f", end="#10554d", light=False),
    dict(key="grad_atardecer", name="Degradado · Atardecer", start="#54243e", end="#773d2c", light=False),
    dict(key="grad_noche", name="Degradado · Noche", start="#111e37", end="#442754", light=False),
    dict(key="grad_mar", name="Degradado · Mar", start="#103954", end="#176164", light=False),
    dict(key="grad_amanecer", name="Degradado · Amanecer", start="#ffe3ca", end="#efd8ed", light=True),
    dict(key="grad_brisa", name="Degradado · Brisa", start="#d9eee5", end="#dce7fa", light=True),
]


def quote_background(size, preset):
    """Render a smooth gradient at export resolution with a small row buffer."""
    start, end = ImageColor.getrgb(preset['start']), ImageColor.getrgb(preset['end'])
    strip = Image.new('RGB', (1, size[1]))
    strip.putdata([tuple(round(a + (b-a) * y / max(1, size[1]-1)) for a, b in zip(start, end))
                   for y in range(size[1])])
    return strip.resize(size)


def create_quote_image(excerpt, source, link, translated=False, title="", color="#b9a0ff", image_bytes=None, original_language="", theme="gris", background="", source_icon=None, show_link=True) :
    """Genera una cita cuadrada de alta resolución para publicar."""
    light = theme == "periodico"
    scale = 2  # 2160 px conserva nitidez tras la compresión de redes sociales.
    image = Image.new("RGB", (1080 * scale, 1080 * scale), "#e6e6e6" if light else "#171b20")
    preset = next((item for item in QUOTE_BACKGROUNDS if item['key'] == background), None)
    if preset:
        image = quote_background(image.size, preset)
        light = preset['light']
        color = "#33354a" if light else "#fff0d2"
    muted = "#525b67" if light else "#c0ccd8"
    border = "#89929b" if light else "#9cabb8"
    drawing = ImageDraw.Draw(image)
    if background == 'choroy':
        # Saturated brand frame, with a dark interior to keep the quote readable.
        drawing.rounded_rectangle((64 * scale, 64 * scale, 1016 * scale, 1016 * scale), radius=24 * scale, fill='#12251E')
        color, border, muted = '#A4D52F', '#A4D52F', '#CDDDD3'
    fonts = Path(__file__).resolve().parent.parent / 'assets' / 'fonts'
    path = str(fonts / 'DejaVuSans.ttf')
    def font_size(size):
        try:
            return ImageFont.truetype(path, size * scale)
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
        title_font = ImageFont.truetype(str(fonts / 'DejaVuSans-Bold.ttf'), 30 * scale)
    except OSError:
        title_font = font_size(30)
    text_width = 880 * scale
    title_lines = wrap_text(title, title_font, text_width)
    title_divider = (205 + len(title_lines) * 40 + 16) * scale
    quote_y = title_divider + 44 * scale
    if image_bytes:
        with Image.open(io.BytesIO(image_bytes)) as cover:
            cover = ImageOps.fit(cover.convert("RGB"), (880 * scale, 240 * scale), method=Image.Resampling.LANCZOS)
            image.paste(cover, (94 * scale, quote_y))
        quote_y += 266 * scale
    spacing = max(200 * scale, 885 * scale - quote_y)
    for size in range(48, 15, -2):
        font = font_size(size)
        lines = wrap_text(excerpt, font, text_width)
        if len(lines) * ((size + 14) * scale) <= spacing and all(drawing.textlength(l, font=font) <= text_width for l in lines):
            break
    drawing.rounded_rectangle((48 * scale, 48 * scale, 1032 * scale, 1032 * scale), radius=28 * scale, outline=border, width=2 * scale)
    drawing.rectangle((94 * scale, 108 * scale, 150 * scale, 114 * scale), fill=color)
    drawing.text((94 * scale, 145 * scale), "CITA EXTRAÍDA DEL ARTÍCULO", font=font_size(20), fill=color)
    drawing.multiline_text((94 * scale, 205 * scale), "\n".join(title_lines), font=title_font, fill=color, spacing=10 * scale)
    drawing.line((94 * scale, title_divider, 986 * scale, title_divider), fill=border, width=2 * scale)
    drawing.multiline_text((94 * scale, quote_y), "\n".join(lines), font=font, fill="#202020" if light else "#edf1f7", spacing=14 * scale)
    drawing.line((94 * scale, 920 * scale, 986 * scale, 920 * scale), fill=border, width=2 * scale)
    language = {"en": "inglés", "es": "español"}.get(original_language)
    origin = "Traducción al español" if translated else ("Versión original en " + language if language else "Versión original")
    source_x = 94 * scale
    if source_icon:
        try:
            with Image.open(source_icon) as favicon:
                favicon = favicon.convert('RGBA')
                favicon.thumbnail((28 * scale, 28 * scale), Image.Resampling.LANCZOS)
                drawing.rounded_rectangle((94 * scale, 936 * scale, 128 * scale, 970 * scale), radius=6 * scale, fill='#FFFFFF')
                image.paste(favicon, (111 * scale - favicon.width // 2, 953 * scale - favicon.height // 2), favicon)
                source_x = 140 * scale
        except (OSError, ValueError):
            pass

    def footer_text(text, font, width):
        if drawing.textlength(text, font=font) <= width:
            return text
        while text and drawing.textlength(text + '…', font=font) > width:
            text = text[:-1]
        return text + '…'

    attribution_width = 780 * scale - source_x
    drawing.text((source_x, 936 * scale), footer_text(source, font_size(18), attribution_width), font=font_size(18), fill=color)
    drawing.text((source_x, 963 * scale), origin, font=font_size(15), fill=muted)
    # Display-only abbreviation: the full article URL remains in metadata and can
    # be copied from the editor. A raster image cannot contain a clickable link.
    compact_link = link.removeprefix('https://').removeprefix('http://')
    if show_link:
        drawing.text((94 * scale, 991 * scale), footer_text('Link: ' + compact_link, font_size(14), 686 * scale), font=font_size(14), fill=muted)

    seal_size = 76 * scale
    seal_x, seal_y = 800 * scale, 936 * scale
    logo_path = Path(__file__).resolve().parent.parent / "assets" / "choroy_reader_logo.png"
    try:
        with Image.open(logo_path) as logo:
            logo = logo.convert("RGBA")
            logo.thumbnail((seal_size, seal_size), Image.Resampling.LANCZOS)
            image.paste(logo, (seal_x, seal_y), logo)
    except (OSError, ValueError):
        pass
    drawing.text((888 * scale, 950 * scale), "Choroy", font=font_size(20), fill=color)
    drawing.text((888 * scale, 978 * scale), "Reader", font=font_size(20), fill=muted)
    image.info["articulo"] = link
    return image
