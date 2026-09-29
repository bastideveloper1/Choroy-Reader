# Choroy Reader

Lector RSS de escritorio en Python con PySide6 y Qt Quick/QML.
La interfaz está en `choroy_reader/qml/main.qml`; el motor de feeds y lectura
en `choroy_reader/core.py` y `choroy_reader/service.py`, independiente de Qt.
`choroy_reader/backend.py` conecta ambas partes y ejecuta las tareas de red
fuera del hilo de la interfaz.

## Ejecutar

Con Python 3.10 o posterior:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
python3 choroy_reader.py
```

El lanzador utiliza automáticamente `.venv` si PySide6 no está disponible
en el intérprete actual. En Windows, el intérprete del entorno es
`.venv\Scripts\python.exe`.

Se actualiza al iniciar y después únicamente con «Actualizar feed».
Para abrir sin actualizar, usar `python3 choroy_reader.py --no-network`.
Esta opción evita la actualización inicial; abrir artículos no descargados
o traducirlos sigue requiriendo conexión.

Se conservan el formato de `config.json` y la carpeta `biblioteca/`
de la versión anterior. Se reutiliza `~/.config/noticias` si contiene la configuración anterior. Las
instalaciones nuevas usan `~/.config/choroy_reader` (bajo `$XDG_CONFIG_HOME`
si está definido). Se puede elegir otra carpeta con `--data-dir RUTA` o
`CHOROY_READER_DATA_DIR`; `MINIMALFEED_DATA_DIR` sigue siendo compatible.
Las citas se exportan en PNG o JPEG y el diálogo propone Descargas.

## Verificar

```bash
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software .venv/bin/python -m unittest discover -s tests -v
```

Las pruebas usan carpetas temporales y datos locales: cubren persistencia,
lectura sin conexión, filtros, radar, destacados, búsqueda desde teclado,
carga de QML y exportación de citas. No consultan servicios de noticias
ni de traducción externos.

Demostración aislada y captura, sin tocar la biblioteca personal:

```bash
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software python3 choroy_reader.py --demo --data-dir /tmp/choroy_reader-demo --smoke-test --screenshot /tmp/choroy_reader.png
```

## Instaladores (preparación)

Se incluyen recetas para Linux y Windows; todavía no se han generado ni
validado instaladores en equipos limpios. Los paquetes no deben incluir
`config.json`, la biblioteca personal ni las cachés del desarrollador.

### Linux Mint / Ubuntu

```bash
.venv/bin/python -m pip install -r requirements_build.txt
.venv/bin/python -m PyInstaller --noconfirm packaging/choroy_reader.spec
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software dist/choroy_reader/choroy_reader --demo --data-dir /tmp/choroy_reader-package-test --smoke-test
.venv/bin/python packaging/build_linux.py --version 0.1.0
```

El resultado esperado es `dist/choroy_reader_0.1.0_amd64.deb` (o `arm64`).
Incluye acceso en el menú de aplicaciones y un ejecutable con Python y Qt.
Se debe construir en la versión más antigua de Linux que se pretenda soportar
para no depender de bibliotecas del sistema más recientes. Antes de distribuir,
validar instalación, apertura, imágenes, citas, red y desinstalación en una máquina
limpia de la distribución objetivo, y completar los avisos de licencia de las
bibliotecas incluidas. La desinstalación no borra la biblioteca del usuario.

### Windows

Construir en Windows con un entorno virtual propio, instalar
`requirements_build.txt` y ejecutar:

```powershell
.venv\Scripts\python.exe -m PyInstaller --noconfirm packaging/choroy_reader.spec
```

Después compilar `packaging/windows.iss` con Inno Setup para crear el asistente
`Choroy Reader-Setup-0.1.0.exe`. Esta receta aún requiere validación en Windows,
incluyendo fuentes tipográficas de las citas y directorios de datos.

Herramientas: [PyInstaller](https://pyinstaller.org/en/stable/usage.html).
No se incluye distribución Android.


## Destacados y lectura sin conexión

Los destacados se guardan automáticamente por artículo y por idioma. Al destacar,
el artículo queda en Guardados para recuperarlo después incluso sin conexión.
Las marcas del original y de la versión en español son independientes: no se
intenta adivinar qué posiciones equivalen entre idiomas.

En el lector, clic derecho → «Destacador» ofrece amarillo, celeste, verde,
rojo pálido y rosa en cualquier tema. Elegir un color pinta la selección actual
y activa el modo de arrastre. Repasar con el mismo color conserva el destacado;
otro color repinta la zona seleccionada. El «Borrador · bloques completos» quita
los bloques que toques con un clic o arrastre, sin dejar fragmentos de esos
bloques. «Quitar este destacado» hace lo mismo desde el menú contextual.

«Descargar todos los artículos» prepara todos los artículos actualmente cargados
en el feed. El diálogo permite incluir sus traducciones al español. Si ya existe
una traducción local, «Leer en español» la muestra inmediatamente; sin esa copia,
la primera traducción requiere conexión. Los errores parciales se informan y no
eliminan originales descargados correctamente.

En Fuentes/Categorías, activa «Atajo web» para añadir una página como enlace
con favicon sin buscar RSS. Los atajos conservan su categoría y no aparecen en
rojo. Edita la entrada existente para convertir una fuente sin feed en atajo.
Los iconos sociales del autor son marcadores visuales sin enlaces por ahora.

Consulta [la revisión de arquitectura](docs/architecture.md) para las decisiones
de persistencia, nombres, compatibilidad y las tareas pendientes antes de publicar.

### Preferencias de lectura

En un artículo, el botón **Aa** permite elegir letra pequeña, mediana, grande o muy grande. En **Configuración → Diseño** puedes guardar el tamaño predeterminado y activar o desactivar las imágenes de los artículos (portada e imágenes intermedias). Las imágenes recuperadas se conservan para las descargas sin conexión.

Al iniciar con un feed guardado, Choroy Reader muestra la copia local. Usa **Actualizar feed** para buscar novedades; las portadas y traducciones ya disponibles se reutilizan. Si aún no hay un feed guardado, la primera carga se inicia automáticamente.

Las imágenes del cuerpo conservan sus proporciones y se colocan junto al texto cuando hay espacio suficiente. Haz clic en una imagen para abrir el visor: permite ampliar, reducir, ajustar a la ventana y desplazarse; se cierra con **Escape** o **Cerrar**.

El botón **Modo lectura** del artículo activa la pantalla completa y oculta la navegación y las acciones secundarias. Usa **Salir del modo lectura** (arriba) o **Escape** para volver a la vista anterior.

**Guardados** muestra primero los artículos añadidos más recientemente, incluso con el radar activo. Los artículos guardados o archivados se ocultan del feed principal y siguen disponibles en sus respectivas listas. Al quitar ambos estados, vuelven a mostrarse si siguen en el feed y dentro del período seleccionado.

### Fuentes sin RSS

Añade la dirección del blog o de su sección de noticias y deja vacía la URL RSS. Si no se detecta un feed, **Actualizar feed** intentará extraer las publicaciones del HTML y sus datos estructurados. Las tarjetas y el lector mostrarán **WEB · Publicación extraída**. Cuando no exista una fecha publicada, se indicará la fecha de detección, que se conserva en actualizaciones posteriores.

Esta extracción no ejecuta JavaScript ni accede a contenido que requiera iniciar sesión. Algunos sitios no exponen sus publicaciones en el HTML y pueden no ser compatibles. Si una extracción posterior no encuentra publicaciones, se conserva la última copia local.

El generador de imágenes de citas ofrece fondos lisos y degradados en **Fondo de la cita**, con colores de texto adaptados al fondo. La vista previa y la exportación PNG/JPG conservan el diseño elegido.
