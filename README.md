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

## Instaladores

Se incluyen recetas para Linux y Windows. La verificación automatizada de Linux
comprueba el arranque del paquete extraído y la conservación de datos de prueba;
no sustituye la instalación en un equipo limpio. Los paquetes no deben incluir
`config.json`, la biblioteca personal ni las cachés del desarrollador.

### Linux Mint / Ubuntu

```bash
.venv/bin/python -m pip install -r requirements_build.txt
.venv/bin/python -m PyInstaller --noconfirm packaging/choroy_reader.spec
.venv/bin/python packaging/build_linux.py
.venv/bin/python packaging/verify_linux.py dist/choroy_reader_0.1.1_amd64.deb
```

El resultado esperado es `dist/choroy_reader_0.1.1_amd64.deb` (o `arm64`).
Incluye acceso en el menú de aplicaciones y un ejecutable con Python y Qt.
La versión se toma de `assets/app_info.json`; el constructor rechaza versiones
distintas, recursos incompletos o datos personales dentro del ejecutable.
También genera un archivo `.deb.sha256` junto al paquete. Para comprobarlo:

```bash
cd dist
sha256sum -c choroy_reader_0.1.1_amd64.deb.sha256
```

Para instalar o actualizar, cierra la aplicación y ejecuta desde la carpeta del
paquete `sudo apt install ./choroy_reader_0.1.1_amd64.deb`. Para una nueva versión,
actualiza `assets/app_info.json` y repite la compilación con un número superior.
El programa se instala en `/opt/choroy_reader`; las preferencias y la biblioteca
se conservan en `~/.config/noticias` o `~/.config/choroy_reader`. Las actualizaciones
son manuales mediante un nuevo `.deb`.

Se debe construir en la versión más antigua de Linux que se pretenda soportar
para no depender de bibliotecas del sistema más recientes. Antes de distribuir,
validar instalación, apertura, imágenes, citas, red y desinstalación en una máquina
limpia de la distribución objetivo, y completar los avisos de licencia de las
bibliotecas incluidas. La desinstalación no borra la biblioteca del usuario.

### Windows

Construir en Windows con un entorno virtual propio, instalar
`requirements_build.txt` y ejecutar:

```powershell
.venv\Scripts\Activate.ps1
python -m pip install -r requirements_build.txt
powershell -ExecutionPolicy Bypass -File packaging/build_windows.ps1
```

El script requiere Inno Setup 6 y crea `dist/Choroy-Reader-Setup-0.1.1-x64.exe`
y su SHA-256. El asistente incluye bienvenida, icono y arte del bosque, idiomas
español/inglés y acceso directo opcional. Instala por usuario sin pedir permisos
de administrador y conserva la biblioteca al actualizar. Construcción para
Windows x64; las comprobaciones bajo Wine no sustituyen las de Windows nativo.
Requiere Windows 10 1809 o posterior, conforme a
[las plataformas admitidas por Qt](https://doc.qt.io/qt-6/windows.html).

Herramientas: [PyInstaller](https://pyinstaller.org/en/stable/usage.html).
No se incluye distribución Android.

Cambios de esta segunda versión: [0.1.1](docs/release-0.1.1.md).
Protecciones y límites de red/contenido: [privacidad](docs/privacy.md).
Comprobación completa: `python packaging/check_release.py`.


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

### Notas en los artículos

Haz clic derecho sobre un pasaje y elige **Añadir nota aquí…**. Aparecerá un
pequeño post-it en el margen, anclado a ese punto del texto incluso al cambiar
el tamaño de letra. Haz clic para abrir el panel de notas a la derecha: puedes
seguir leyendo, seleccionando y desplazándote por el artículo a la izquierda.
La navegación lateral se oculta temporalmente para dejar espacio. **Ampliar nota**
ocupa casi toda la ventana; **Volver junto al artículo** recupera la vista dividida.

Cada nota conserva su tema: **Periódico** (papel claro), **Gris** (oscuro) o
**Post-it** (cinco colores). Los colores también identifican la nota en el margen.
Se guarda automáticamente y al cerrar o cambiar de artículo.

Coloca el cursor donde quieras e inserta una imagen con **＋ Imagen**. Puedes
arrastrarla a otro punto del texto, hacer clic para elegir **Izquierda**, **Derecha**
o **En línea**, y ajustar su tamaño con **− / +**. El texto rodea las imágenes
laterales. La pequeña **× roja** de su esquina elimina la imagen; **Ctrl+Z**
permite deshacer la edición mientras la nota sigue abierta.

Las imágenes se conservan dentro de la nota y funcionan sin conexión aunque
se borre el archivo original. Se admiten archivos de hasta 20 MB, ajustados a un
máximo de 1600 píxeles por lado. Las notas anteriores conservan su texto e imágenes.

Crear una nota añade el artículo a Guardados. Las notas del original y de la
traducción son independientes y se incluyen en la copia de seguridad de la
aplicación. **Eliminar nota** pide confirmación antes de borrar su contenido.

En el lector, el radar está junto a **Volver al feed** y la búsqueda aparece
bajo la portada. La barra de acciones reúne archivar, guardar, descargar,
traducir, tamaño de letra, modo lectura y abrir original; **No me interesa**
queda al extremo derecho.

En el generador de citas, **Mostrar idioma original** alterna con la traducción.
Si creaste la cita desde el artículo traducido, primero permite seleccionar
el pasaje correspondiente del original. Después puedes alternar entre ambas
versiones sin perder la selección ni reconstruir el original mediante traducción.

### Actualizaciones del programa

En **Configuración → Acerca de Choroy Reader → Actualizaciones**, pulsa
**Buscar actualizaciones**. La consulta manual a GitHub incluye publicaciones beta
con etiquetas numéricas como `v0.1.1`. Si hay una versión superior, muestra sus
novedades y **Descargar nueva versión** abre la publicación para elegir el instalador.
La consulta requiere conexión y no instala nada automáticamente. Cierra la aplicación
antes de instalar el nuevo paquete; tu biblioteca y preferencias se conservan.

La versión 0.1.1 incorpora esta función. Quienes tengan 0.1.0 deben descargar e
instalar 0.1.1 manualmente para poder consultar las siguientes actualizaciones.

### El Bosque: revisión de fuentes

Abre **El Bosque** desde la barra lateral. Permite comparar fuentes por mes o
por todo el historial registrado, ordenar por actividad y uso, y decidir cuáles
conservar. Los datos se guardan localmente en SQLite y viajan en la copia de
seguridad; no se envían a servicios de métricas.

Cada cifra cuenta **artículos distintos** por fuente, acción y período: recibidos,
abiertos, destacados, favoritos añadidos manualmente, citas exportadas y marcados
«No me interesa». Repetir una acción sobre el mismo artículo en el mismo mes no
incrementa el contador. El histórico cuenta artículos únicos, no la suma de los
meses. Deshacer una acción no borra que ocurrió. Una cita exportada no implica
que se haya publicado en una red social.

El registro empieza al incorporar esta función, sin inventar actividad anterior.
«Recibidos» mide artículos nuevos detectados al actualizar, condicionado por los
períodos y límites de las fuentes; no mide toda su producción real. Radar muestra
artículos evaluados y coincidencias observadas durante actualizaciones, usando
los intereses y equivalencias configurados entonces. Si no hay intereses no se
evalúa; «Sin evaluar» es diferente de cero coincidencias. Cambiar intereses no
reescribe las métricas anteriores. Los atajos web no se incluyen como fuentes.

**Conservar** marca la revisión como hecha y propone volver en 30 días.
**Posponer** aplaza 30 días la revisión sin detener la recepción de artículos.
**Revisar ahora** vuelve a marcarla pendiente. Al vencer el plazo vuelve a aparecer
pendiente al abrir El Bosque o reiniciar la aplicación. **Eliminar fuente** pide
confirmación y la quita de todas sus categorías, conservando los artículos de la
biblioteca y las métricas. Las fuentes eliminadas dejan de aparecer en la lista;
si se añade nuevamente la misma URL se recuperan sus estadísticas.

El Bosque se abre en pantalla completa con una bienvenida ilustrada que permanece hasta
que pulses **Haz clic para entrar en El Bosque**, hagas clic en el fondo o uses Escape. Las métricas se presentan en tarjetas junto al promedio
del período y la fuente aparece con su favicon (o su inicial si no está disponible).
**Salir de El Bosque** restaura el tamaño anterior de la ventana. Escape durante
la revisión también permite salir.

La bienvenida usa `choroybosque.png` en el tema claro y `choroybosquenoche.png`
en los oscuros, con las mismas dimensiones. Cada métrica muestra una carita:
😄 para actividad favorable respecto del promedio, 😴 para desfavorable y
😐 dentro del ±20 % del promedio o cuando no hay actividad para comparar.
El emoji lleva un fondo verde (favorable), rojo (desfavorable) o azul (neutral),
adaptado al tema claro u oscuro. En «No me interesa» la valoración se invierte: menos descartes es favorable.
Al pasar el cursor sobre la carita se explica la comparación; es una referencia
de actividad, no una evaluación automática de calidad de la fuente.

### Navegación y aspecto

La identidad de Choroy Reader aparece en la cabecera de la barra lateral.
**El Bosque** y **Gestionar fuentes** están agrupados en **Fuentes**; El Bosque
usa `assets/bosqueicon.png`. En el feed, los atajos fijados aparecen encima de
las categorías horizontales. Selecciona una categoría para ver sus fuentes;
el clic derecho permite administrarlas y se conserva el arrastre para reordenar.
Los temas claro y oscuro comparten los verdes de Choroy y usan superficies,
bordes y textos adaptados al contraste de cada fondo.

Para preparar una cita, el menú de clic derecho del artículo permite elegir
**Cita en una parte** o **Cita en dos partes** antes de seleccionar. Arrastra sobre
el texto: el panel muestra los caracteres disponibles en tiempo real. En dos
partes, pulsa **Guardar primera parte**, desplázate y selecciona el segundo
pasaje; **Crear imagen** los une en orden de lectura con `[…]`. El límite total
es de 500 caracteres, incluido el separador; los pasajes no pueden superponerse.
Puedes cancelar o volver a seleccionar si excedes el límite. La selección se
reinicia al cambiar de artículo o idioma.

En el editor de citas, **Mostrar enlace** y **Mostrar icono de la web** son
independientes. El enlace está oculto inicialmente; el icono se muestra si está
disponible. **Copiar enlace** sigue disponible aunque no aparezca en la imagen.
