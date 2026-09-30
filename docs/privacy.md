# Contenido y privacidad en 0.1.1

Las noticias se convierten a texto y no se ejecutan como páginas web: el lector
no carga JavaScript, formularios ni marcos de las fuentes. Los títulos con
resaltados se escapan antes de añadir formato; las etiquetas y nombres se
muestran como texto plano.

Las descargas de fuentes admiten solo HTTP/HTTPS sin credenciales en la URL.
Las conexiones comprueban las direcciones IP resueltas y se conectan a esas
mismas direcciones: se rechazan destinos privados, locales y reservados,
incluidas las redirecciones. Se rechaza también pasar de HTTPS a HTTP.
Se conservan la comprobación de certificados TLS y los tiempos de espera.
No se utilizan cookies, cabeceras Referer ni proxies del entorno para estas
descargas. Esto significa que los feeds de intranet y las redes que exijan
un proxy no están soportados por esta ruta de descarga.

Cada respuesta y su contenido descomprimido están limitados a 16 MiB.
Las imágenes de fuentes se limitan a 20 megapíxeles y a formatos raster
JPEG, PNG, WebP, GIF, ICO o BMP: se rechazan SVG, EPS y contenido que no sea
una imagen admitida. Las imágenes del lector se descargan y se incrustan
localmente. Esto reduce la exposición, pero no constituye una garantía de
ausencia de vulnerabilidades en los decodificadores.

Las fuentes y sus servidores de imágenes siguen viendo la IP de quien hace
la petición. El lector no es un anonimizador ni elimina todas las posibilidades
de seguimiento mediante URL de imágenes. La traducción envía el texto a Google
Translate cuando se solicita o está habilitada para una fuente. Puede
desactivarse en la configuración de cada fuente. La consulta manual de
actualizaciones contacta GitHub. Los enlaces externos y las redes del autor
se abren en el navegador al pulsarlos, bajo las preferencias de ese navegador.

Preferencias, artículos, índices y notas se guardan localmente. El índice FTS5
es temporal y reside en memoria. Los instaladores se construyen con el código
y los recursos de la aplicación, sin la biblioteca, configuración o cachés
personales del desarrollador. Actualizar o desinstalar el programa conserva
los datos del usuario.

Pruebas de regresión: `tests/test_source_security.py`, `tests/test_qt.py`
y `tests/test_portability.py`.

Referencias técnicas usadas en la revisión:
- [Redirecciones HTTP de Python](https://docs.python.org/3/library/urllib.request.html)
- [Seguridad de imágenes en Pillow](https://pillow.readthedocs.io/en/stable/handbook/security.html)
