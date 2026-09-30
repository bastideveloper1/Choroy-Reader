# Verificación final de 0.1.1

Fecha: 30 de septiembre de 2026.

- Revisión previa: 119 pruebas, ejecutadas en 77 procesos/grupos, sin fallos.
  Qt se prueba de forma aislada para evitar el fallo acumulado de destrucción
  de motores QML observado en el arnés de pruebas.
- Windows bajo Wine: 20 pruebas de biblioteca y 7 de seguridad correctas;
  FTS5 también se comprobó con Python para Windows.
- Pruebas específicas tras los últimos ajustes: redes y fuente de interfaz,
  atajos desplegables, disposición de navegación y conservación del scroll.
- Ambos ejecutables empaquetados arrancaron con datos sintéticos y conservaron
  artículos guardados, notas y destacados. La interfaz de Windows se revisó
  visualmente tras cargar la tipografía incluida.
- El .deb final coincide con el QML y los metadatos de redes del código final;
  su SHA-256 fue comprobado.
- El instalador Windows final se instaló correctamente en un prefijo Wine
  aislado. El QML, metadatos y tipografía instalados coinciden byte a byte con
  los archivos finales. No se incluyen configuración ni biblioteca personal.
- Windows fue compilado y probado bajo Wine; no se realizó una prueba en un
  equipo Windows nativo. La adaptación de ICU usada para el entorno de
  compilación no se distribuye dentro del paquete.

Artefactos en `dist/0.1.1/`:

- `Linux/choroy_reader_0.1.1_amd64.deb`
- `Windows/Choroy-Reader-Setup-0.1.1-x64.exe`
- `SHA256SUMS.txt`

Se generó también un `.sha256` para cada instalador. El release no se ha
publicado en GitHub ni se ha instalado en el sistema personal del usuario.
