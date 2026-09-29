"""Extract publication links from server-rendered HTML, without executing scripts."""
import json
from urllib.parse import urljoin, urlsplit, urlunsplit, parse_qsl, urlencode
from bs4 import BeautifulSoup


def extract_publications(html, base_url, maximum=1000):
    soup = BeautifulSoup(html, 'html.parser')
    host = urlsplit(base_url).hostname or ''
    entries = {}

    def clean_url(value):
        if not isinstance(value, str) or not value.strip() or value.startswith('#'):
            return None
        try:
            parts = urlsplit(urljoin(base_url, value))
        except ValueError:
            return None
        if parts.scheme not in ('http', 'https') or (parts.hostname or '').removeprefix('www.') != host.removeprefix('www.'):
            return None
        if parts.path.rstrip('/') == urlsplit(base_url).path.rstrip('/') and not ({k for k, _ in parse_qsl(parts.query)} & {'p', 'id', 'post', 'article'}):
            return None
        segments = set(parts.path.lower().strip('/').split('/'))
        if segments & {'tag', 'tags', 'category', 'categories', 'categoria', 'categorias', 'author', 'autor', 'login', 'contact', 'contacto', 'privacy', 'privacidad'}:
            return None
        query = urlencode([(k, v) for k, v in parse_qsl(parts.query) if not k.startswith('utm_') and k not in {'fbclid', 'gclid'}])
        return urlunsplit((parts.scheme, parts.netloc, parts.path, query, ''))

    def add(title, link, image=None, date=None):
        link = clean_url(link)
        title = ' '.join(str(title or '').split())
        if not link or len(title) < 8 or len(entries) >= maximum:
            return
        if isinstance(image, list):
            image = image[0] if image else None
        if isinstance(image, dict):
            image = image.get('url') or image.get('contentUrl')
        image = urljoin(base_url, image) if isinstance(image, str) else None
        if image and urlsplit(image).scheme not in ('https', 'http'):
            image = None
        entry = entries.setdefault(link, [title, link, image, date])
        entry[2] = entry[2] or image
        entry[3] = entry[3] or date

    def structured(value):
        if isinstance(value, list):
            for item in value:
                structured(item)
        elif isinstance(value, dict):
            types = value.get('@type', [])
            types = [types] if isinstance(types, str) else types if isinstance(types, list) else []
            if any(t in {'Article', 'NewsArticle', 'BlogPosting', 'Report', 'ListItem'} for t in types if isinstance(t, str)):
                item = value.get('item', value)
                if isinstance(item, dict):
                    add(item.get('headline') or item.get('name'), item.get('url') or item.get('@id'), item.get('image'), item.get('datePublished'))
            for child in value.values():
                if isinstance(child, (dict, list)):
                    structured(child)

    for script in soup.select('script[type="application/ld+json"]'):
        try:
            structured(json.loads(script.string or script.get_text()))
        except (ValueError, TypeError, RecursionError):
            continue
    for node in soup.select('script, style, nav, header, footer, aside, form'):
        # Article headers often contain the publication's title.
        if node.name == 'header' and node.find_parent('article'):
            continue
        node.decompose()
    for anchor in soup.select('article a[href], h2 a[href], h3 a[href], a[rel~="bookmark"], a:has(h2), a:has(h3)'):
        heading = anchor.find(['h1', 'h2', 'h3']) or anchor.find_parent(['h1', 'h2', 'h3'])
        card = anchor.find_parent('article') or (heading.parent if heading and heading.parent.name != 'a' else anchor.parent)
        title = heading.get_text(' ', strip=True) if heading else anchor.get_text(' ', strip=True)
        if not heading and 'bookmark' not in (anchor.get('rel') or []):
            # Avoid secondary actions and author/category links inside a card.
            if card.find(['h1', 'h2', 'h3']):
                continue
        picture = card.find('img')
        image = (picture.get('data-src') or picture.get('src')) if picture else None
        date = card.find('time')
        add(title, anchor.get('href'), image, date.get('datetime') if date else None)
    return [tuple(entry) for entry in entries.values()]
