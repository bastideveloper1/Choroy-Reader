"""Consulta manual de publicaciones públicas; no instala ni ejecuta descargas."""
import json
import re
from urllib.request import Request, urlopen
from urllib.parse import urlsplit


def version_key(value):
    match = re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)', value)
    return tuple(map(int, match.groups())) if match else None


def check_updates(repository, installed):
    parsed = urlsplit(repository)
    if parsed.scheme != 'https' or parsed.netloc != 'github.com':
        raise ValueError('Repositorio de actualizaciones inválido')
    path = parsed.path.strip('/')
    if not re.fullmatch(r'[\w.-]+/[\w.-]+', path):
        raise ValueError('Repositorio de actualizaciones inválido')
    current = version_key(installed)
    if current is None:
        raise ValueError('Versión instalada inválida')
    releases = []
    for page in range(1, 11):
        request = Request(f'https://api.github.com/repos/{path}/releases?per_page=100&page={page}',
                          headers={'Accept': 'application/vnd.github+json',
                                   'User-Agent': 'Choroy-Reader', 'X-GitHub-Api-Version': '2022-11-28'})
        with urlopen(request, timeout=15) as response:
            batch = json.load(response)
        if not isinstance(batch, list):
            raise ValueError('Respuesta de GitHub inválida')
        releases.extend(batch)
        if len(batch) < 100:
            break
    else:
        raise ValueError('Demasiadas publicaciones para completar la consulta')
    candidates = [(version_key(r.get('tag_name', '')), r) for r in releases
                  if isinstance(r, dict) and not r.get('draft')]
    candidates = [(v, r) for v, r in candidates if v is not None]
    result = dict(busy=False, available=False, version='', notes='', url='', message='No hay versiones publicadas compatibles.')
    if not candidates:
        return result
    version, release = max(candidates, key=lambda item: item[0])
    newer = version > current
    tag = release['tag_name']
    result.update(available=newer, version=tag, notes=release.get('body') or '',
                  url=f'https://github.com/{path}/releases/tag/{tag}',
                  message=(f'Actualización disponible: {tag}' if newer else 'Tu versión está al día.')
                          + (' · Beta' if release.get('prerelease') else ''))
    return result
