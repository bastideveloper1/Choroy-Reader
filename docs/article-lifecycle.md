# Ciclo de vida de los artículos

La identidad es la URL exacta del artículo. La misma URL no genera dos entradas
en una colección. URLs diferentes, incluso con parámetros de seguimiento, se
consideran distintas; no se fusionan por título.

## Feed e historial

- Una actualización correcta reemplaza el conjunto recibido de cada fuente.
  Los artículos que dejan de venir salen del feed, pero permanecen en Historial.
- Si una fuente falla o se cancela la actualización, se conserva su feed anterior.
- El listado del feed filtra por el período configurado (hoy por defecto), excluye
  fechas desconocidas o futuras y oculta archivados. El límite por fuente se aplica
  al recibir artículos. Cambiar el período requiere actualizar para buscar más.
- Historial conserva los metadatos de todos los artículos recibidos por esta
  versión: título, URL, fuente, fecha e idioma. No depende del período actual.
  Incluye también artículos leídos, descartados y archivados.
- Al iniciar, se incorporan al historial las entradas existentes del feed,
  guardados, descargas y archivados. No es posible recuperar metadatos que ya
  se hubieran eliminado antes de esta función.
- La retención es configurable en Fuentes y categorías: sin límite (por defecto),
  1, 7, 30, 90, 180 o 365 días desde la primera recepción. Se aplica al iniciar,
  actualizar y modificar la preferencia. Para instalaciones anteriores el plazo
  comienza cuando se registra por primera vez la identidad persistente.
- No se retiran artículos no leídos, guardados (favoritos), archivados ni
  descargados. Retirar una fuente no elimina estas protecciones.
- Los metadatos retirados pasan a `biblioteca/retirados` durante 30 días;
  «Recuperar historial retirado» permite restaurarlos y reinicia su plazo.
  Transcurrida la recuperación, se eliminan esos metadatos.
- La tabla SQLite `article_identity` conserva URL, primera recepción y fecha de
  retirada. El RSS no vuelve a crear un historial ya retirado. Si vuelve a aparecer
  en el feed, mantiene sus estados de leído y descartado, conservados en config.
  Las identidades mínimas no caducan. La limpieza de historial no elimina caché,
  textos, destacados ni colecciones personales.

## Estados y colecciones personales

Marcar como leído **nunca elimina** un artículo, archivo ni texto. Cambia el estado
persistente y coloca el artículo después de los no leídos en el feed. Descartar
lo coloca después de los leídos; tampoco elimina contenido. Guardado, leído,
archivado y descartado son independientes.

Archivar oculta del feed y conserva una copia en Archivados. Restaurar devuelve
la copia al conjunto local del feed (sujeto a fecha y fuente); una actualización
posterior puede retirarla si ya no viene en RSS, pero sigue en Historial.

Quitar un guardado, desarchivar o eliminar una descarga solo afecta a esa
colección. Los estados de lectura/descarte y el historial permanecen. Deshacer
una lectura masiva restaura solo los estados modificados por esa operación y
respeta cambios manuales posteriores.

## Caché y lectura sin conexión

- `biblioteca/feed`: última copia recibida, depurada al actualizar correctamente.
- `biblioteca/historial`: metadatos permanentes; no duplica imágenes ni cuerpos.
- `biblioteca/guardados`, `archivados`: copias personales; no caducan por RSS.
- `biblioteca/descargas`: copia explícita con texto e imagen disponibles. Es la
  garantía de lectura sin conexión y se elimina solo por la acción correspondiente
  o al cancelar una operación que la haya creado.
- `reader_state.sqlite3`: originales leídos, traducciones y destacados. No caducan
  cuando el artículo sale del RSS ni al eliminar una descarga. Los destacados
  permanecen ligados a la versión del texto sobre la que se crearon.
- `cache/images`, `cache/favicons`: recursos visuales sin depuración automática.
  El contenido RSS auxiliar y el diccionario de lectura en memoria se pierden
  al cerrar; las instantáneas SQLite permanecen.

El historial permite abrir el original, usar un texto previamente almacenado o
intentar recuperarlo de la web. No promete recuperar texto nunca descargado si
la página original deja de estar disponible.

## Punto de lectura

El menú de clic derecho del lector permite guardar una posición explícita. Se
persisten el offset UTF-16, la longitud y el porcentaje del texto, por URL y por
versión (original/español), en `progreso_lectura` de config.json. «Continuar desde
aquí» desplaza el lector a esa posición. Guardar el punto no marca como leído,
no modifica destacados y no garantiza una descarga sin conexión.
