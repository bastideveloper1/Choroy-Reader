"""Bounded, stateless HTTP downloads for untrusted news sources."""
import gzip
import http.client
import io
import ipaddress
import socket
import urllib.parse
import urllib.request

MAX_DOWNLOAD = 16 * 1024 * 1024


def validate_url(url):
    parts = urllib.parse.urlsplit(url)
    if (parts.scheme not in {'http', 'https'} or not parts.hostname
            or parts.username is not None or parts.password is not None
            or any(ord(c) < 32 or ord(c) == 127 for c in url)):
        raise ValueError('La fuente debe usar una URL HTTP o HTTPS sin credenciales')
    # Also reject malformed ports before handing a URL to urllib.
    parts.port
    return parts


def public_connection(address, timeout=socket._GLOBAL_DEFAULT_TIMEOUT,
                      source_address=None, **kwargs):
    host, port = address
    addresses = socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM)
    # Validate the actual addresses that will be connected, without resolving again.
    for family, kind, proto, canon, target in addresses:
        ip = ipaddress.ip_address(target[0].split('%')[0])
        if (not ip.is_global or ip.is_multicast or ip.is_reserved
                or (ip.version == 6 and ip.ipv4_mapped and not ip.ipv4_mapped.is_global)):
            raise ValueError('Se bloqueó una conexión de la fuente a una dirección privada o local')
    last_error = OSError('No se encontró una dirección pública para la fuente')
    for family, kind, proto, canon, target in addresses:
        connection = socket.socket(family, kind, proto)
        try:
            if timeout is not socket._GLOBAL_DEFAULT_TIMEOUT:
                connection.settimeout(timeout)
            if source_address:
                connection.bind(source_address)
            connection.connect(target)
            return connection
        except OSError as error:
            last_error = error
            connection.close()
    raise last_error


class PublicHTTPConnection(http.client.HTTPConnection):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._create_connection = public_connection


class PublicHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._create_connection = public_connection


class PublicHTTPHandler(urllib.request.HTTPHandler):
    def http_open(self, req):
        return self.do_open(PublicHTTPConnection, req)


class PublicHTTPSHandler(urllib.request.HTTPSHandler):
    def https_open(self, req):
        return self.do_open(PublicHTTPSConnection, req, context=self._context)


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_url(newurl)
        if req.type == 'https' and urllib.parse.urlsplit(newurl).scheme != 'https':
            raise ValueError('Se bloqueó una redirección de HTTPS a HTTP')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download(url, timeout=10):
    validate_url(url)
    request = urllib.request.Request(url, headers={
        'User-Agent': 'ChoroyReader/0.1.1',
        'Accept': '*/*', 'Accept-Language': 'en-US,en;q=0.9,es;q=0.8',
    })
    # No cookie jar, Referer, credentials, or environment proxies for source requests.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), SafeRedirect(),
                                         PublicHTTPHandler(), PublicHTTPSHandler())
    with opener.open(request, timeout=timeout) as response:
        data = response.read(MAX_DOWNLOAD + 1)
        if len(data) > MAX_DOWNLOAD:
            raise ValueError('La descarga supera el límite de 16 MiB')
        if response.info().get('Content-Encoding', '').lower() == 'gzip':
            with gzip.GzipFile(fileobj=io.BytesIO(data)) as compressed:
                data = compressed.read(MAX_DOWNLOAD + 1)
            if len(data) > MAX_DOWNLOAD:
                raise ValueError('El contenido descomprimido supera el límite de 16 MiB')
        return data
