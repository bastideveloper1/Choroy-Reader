# MinimalFeed

Lector RSS de escritorio en Python con PySide6 y Qt Quick/QML.
La interfaz está en `minimalfeed/qml/Main.qml`; el motor de feeds y lectura
en `minimalfeed/core.py` y `minimalfeed/service.py`, independiente de Qt.
`minimalfeed/backend.py` conecta ambas partes y ejecuta las tareas de red
fuera del hilo de la interfaz.

## Ejecutar

Con Python 3.10 o posterior:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
python3 noticias.py
```

El lanzador utiliza automáticamente `.venv` si PySide6 no está disponible
en el intérprete actual. En Windows, el intérprete del entorno es
`.venv\Scripts\python.exe`.

Se actualiza al iniciar y después únicamente con «Actualizar feed».
Para abrir sin actualizar, usar `python3 noticias.py --no-network`.
Esta opción evita la actualización inicial; abrir artículos no descargados
o traducirlos sigue requiriendo conexión.

Se conservan el formato de `config.json` y la carpeta `biblioteca/`
de la versión anterior. Por defecto se usa `~/.config/noticias`
(o `$XDG_CONFIG_HOME/noticias`). Se puede elegir otra carpeta con
`--data-dir RUTA` o `MINIMALFEED_DATA_DIR`.
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
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software python3 noticias.py --demo --data-dir /tmp/minimalfeed-demo --smoke-test --screenshot /tmp/minimalfeed.png
```

La migración actual corresponde a escritorio. No incluye un paquete
Android ni instaladores de distribución.
