# Choroy Reader: arquitectura y revisión

## Capas

- `choroy_reader.py`: arranque y selección del entorno Python.
- `choroy_reader/app.py`: composición de servicios, Qt y QML.
- `choroy_reader/core.py`: RSS/Atom, extracción, traducción y generación de citas.
- `choroy_reader/service.py`: coordinación de lectura, fuentes, iconos y filtros.
- `choroy_reader/library.py`: persistencia atómica de guardados/descargas y búsqueda.
- `choroy_reader/reader_store.py`: SQLite para originales, traducciones y destacados.
- `choroy_reader/backend.py`: puente Qt; estado observable y acciones de interfaz.
- `choroy_reader/qml/main.qml`: presentación e interacciones.

Los servicios de red y almacenamiento no importan Qt. El puente inicia tareas
fuera del hilo gráfico y devuelve resultados mediante señales; los cambios del
estado visual se aplican en el hilo principal. Los servicios se inyectan al
construir el puente para poder probarlos sin conexión.

## Nombres y compatibilidad

Variables, funciones propias, identificadores QML y módulos usan inglés y
`snake_case`. Las clases mantienen `PascalCase`, las constantes `UPPER_SNAKE_CASE`
y las APIs que Qt impone conservan sus nombres, por ejemplo `modelData`,
`onClicked` y `openUrl`. Cambiar esos nombres rompería la integración.

Las claves del JSON existente (`categorias`, `titulo`, etc.) y las carpetas
`biblioteca/guardados` y `biblioteca/descargas` son un contrato de compatibilidad,
no variables Python. Se conservan para abrir datos anteriores sin una migración
destructiva. Si existe `~/.config/noticias/config.json`, se sigue usando esa
ubicación; las instalaciones nuevas usan `~/.config/choroy_reader`.

## Lectura persistente

`reader_state.sqlite3` conserva una instantánea original por URL, su traducción
y dos juegos separados de rangos de destacado. Los offsets usan unidades UTF-16,
como Qt. Un cambio de idioma limpia el formato anterior antes de reemplazar el
texto y restaura únicamente los rangos del idioma mostrado. La búsqueda no
modifica los destacados persistidos.

El original queda estable para no aplicar posiciones antiguas sobre una revisión
diferente del artículo. Destacar guarda el artículo en Guardados; las descargas
masivas guardan texto e imagen sin eliminar descargas anteriores. La traducción
anticipada es opcional y sus errores se informan sin perder el original.
SQLite usa transacciones y conexiones independientes por operación. Los JSON
se reemplazan de manera atómica. Los datos personales no entran al instalador.

## Fuentes y atajos

`source_type` distingue `feed` de `shortcut`; una entrada antigua se interpreta
como fuente RSS. Los atajos no intentan detectar feeds, no producen tarjetas y
no reciben el aviso rojo. Una página puede cambiar de tipo editando su entrada.
No se permite duplicar la misma URL dentro de una categoría. Los favicons se
obtienen del propio sitio, se validan como imagen y se guardan localmente; si
fallan, se conserva el nombre como enlace utilizable.

## Alcance de la revisión

Se corrigieron el estado efímero del lector, la pérdida de la URL de fuente en
los archivos guardados, el uso accidental de truthiness de elementos XML para
las fechas y las llamadas pendientes a una interfaz Qt destruida. Las pruebas
cubren persistencia, compatibilidad, interacción QML, traducción en caché y
separación entre atajos y RSS. No validan la disponibilidad de sitios externos.

La arquitectura tiene capas útiles, pero no se considera una revisión de
seguridad ni una garantía de ausencia de errores. El puente y QML aún concentran
varias pantallas; extraer componentes por pantalla es una mejora futura razonable.
Antes de distribuir siguen pendientes la validación de instaladores en equipos
limpios, fuentes tipográficas en Windows, pruebas de red reales y los avisos de
licencias. No se añadieron instaladores nuevos durante esta revisión.
