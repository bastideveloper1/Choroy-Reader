# Choroy Reader 0.1.1 · Segunda versión

- Atajos web debajo de las categorías, plegados por defecto y desplegables
  en una lista vertical con desplazamiento y reordenación.
- Redes del autor activas: GitHub, Instagram y Mastodon; se elimina Twitter/X.
- Se conserva la posición del feed al descartar, guardar, archivar o marcar
  como leída una noticia; el final de la lista se ajusta cuando se eliminan filas.
- Búsqueda FTS5 en títulos, contenido y traducciones guardadas, con alternativa
  cuando la biblioteca SQLite no proporciona el tokenizador requerido.
- Protección de descargas, destinos de red, texto e imágenes no confiables.
  Véase [la revisión de privacidad](privacy.md) y sus límites.
- Instalación de Windows con identidad visual, icono, bienvenida en español
  e información sobre conservación de los datos.

Las comprobaciones de Qt se ejecutan en procesos independientes para evitar
los cierres acumulados observados al destruir varios motores QML en un mismo
proceso de pruebas. Ejecutar `python packaging/check_release.py`.

Los paquetes son actualizaciones manuales; no se publica un release ni se
instala el programa en el equipo del desarrollador durante la construcción.
