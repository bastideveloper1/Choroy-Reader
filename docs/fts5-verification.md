# Verificación de búsqueda FTS5

Verificado el 30 de septiembre de 2026:

| Entorno | Python | SQLite | FTS5 con trigramas | Resultado |
| --- | --- | --- | --- | --- |
| Linux nativo | 3.12.3 | 3.45.1 | Disponible | 3 pruebas del índice correctas |
| Binarios oficiales Windows x64 bajo Wine | 3.12.10 | 3.49.1 | Disponible | Las mismas 3 pruebas correctas |

La prueba de Windows utiliza el paquete embebido oficial de python.org,
incluida su biblioteca SQLite para Windows. No constituye una prueba en
Windows nativo ni del instalador o de la interfaz gráfica empaquetada.

Las pruebas comparan FTS5 con la búsqueda alternativa: acentos, mayúsculas,
Unicode, frases literales, comillas, operadores, consultas cortas, cuerpos,
cambios de documentos, eliminaciones y cambios de colección. También simulan
una biblioteca SQLite sin FTS5 para verificar la activación de la alternativa.
La integración con artículos guardados comprueba títulos traducidos, texto
original y traducciones persistidas, y la exclusión del contenido cuando
la búsqueda en cuerpos está desactivada.

Repetir desde la raíz del proyecto con el intérprete del entorno:

```sh
python -m unittest discover -s tests -p test_search_index.py
python -m unittest discover -s tests -p test_library.py
```

Las pruebas del índice pueden funcionar sin FTS5; para comprobar explícitamente
que el entorno proporciona FTS5 con trigramas:

```sh
python -c "from choroy_reader.search_index import SearchIndex; i = SearchIndex(); print(i.available); assert i.available; i.close()"
```

El índice es temporal y reside en memoria; no migra la biblioteca del usuario.
Si SQLite no ofrece FTS5 o su tokenizador de trigramas, se utiliza la búsqueda
literal alternativa. La compatibilidad comprobada corresponde a las versiones
de la tabla, no a todas las versiones de Python ni a todos los paquetes Windows.
