# Respaldo y portabilidad

En **Fuentes y categorías → Respaldo y portabilidad** hay cuatro acciones.

## Importar y exportar OPML

OPML intercambia fuentes y categorías; no incluye artículos ni preferencias.
Se exporta OPML 2.0 con `xmlUrl` para RSS y `htmlUrl` para el sitio web. Los atajos
y fuentes cuyo RSS aún no se conoce se exportan como enlaces, con atributos
propios para conservar su tipo al volver a importarlos en Choroy Reader.
Otros lectores pueden ignorar estos atributos y los enlaces sin RSS.

La importación combina con la configuración actual. Omite URLs inválidas y
entradas repetidas por URL del sitio o del RSS dentro de una misma categoría.
No reemplaza fuentes existentes. Las categorías anidadas se aplanan con `/`.
Después de importar, pulsa Actualizar feed para obtener sus artículos.
Referencia del formato: https://opml.org/spec2.opml

## Copia local ZIP

La copia contiene la configuración completa, todas las colecciones disponibles
(feed, historial, retirados, guardados, descargas y archivados), la base SQLite
(textos, traducciones, destacados e identificadores mínimos), caché visual y los
iconos personalizados que aún existen. Los iconos se incluyen en la copia y sus
rutas se adaptan al destino al restaurar. Los estados, progreso de lectura,
equivalencias del radar, retención y demás preferencias están en la configuración.

No incluye código, entorno Python ni otras copias de seguridad. El ZIP no está
cifrado: guárdalo como un archivo personal. No es necesario usar servicios externos.
La instantánea SQLite se obtiene mediante su API de backup. La salida final
reemplaza el archivo de destino solo cuando termina de construirse.

## Restaurar

Restaura una copia creada por Choroy Reader, reemplazando los datos actuales.
La interfaz pide confirmar y crea previamente `backups/antes-de-restaurar-*.zip`.
Esa copia automática puede restaurarse con la misma acción.

Antes de reemplazar archivos se validan la versión, rutas, integridad SHA-256,
configuración, colecciones y base de datos. La extracción se hace en una carpeta
temporal; se rechazan rutas externas y duplicadas. Si falla el reemplazo durante
la operación, se restituyen los archivos anteriores. No se tocan archivos de
código presentes en la carpeta de datos.

Las acciones esperan a que terminen las tareas de fondo y bloquean temporalmente
la interacción mientras trabajan, para no mezclar actualizaciones con una copia.
Al terminar la restauración, la interfaz carga los datos recuperados sin reiniciar.
La limpieza por retención no se ejecuta en la restauración; vuelve a aplicarse
según lo configurado en el siguiente inicio o actualización.
