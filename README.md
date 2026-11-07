# MapReduce de palabras frecuentes en textos de México

## Objetivo
Contar cuántas veces aparece cada palabra en el campo `text` de los registros JSON.

## Flujo
- Map: transformar cada palabra en el par (palabra, 1).
- Reduce: sumar los valores de cada palabra.
- Comparación: validar el resultado paralelo contra una versión secuencial.

## Dataset
Los archivos JSON están dentro de un ZIP. No subir el ZIP ni los datos a Git.
El programa los leerá por streaming para no cargar todo el dataset en memoria.

## Convenciones iniciales
- Convertir palabras a minúsculas y conservar letras acentuadas.
- Ignorar signos de puntuación, números y guiones bajos; no excluir palabras vacías.
- Mostrar las 20 palabras más frecuentes.

## Probar la versión secuencial

Instala las dependencias y ejecuta las pruebas:

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

Ejecuta el conteo con la ruta al ZIP:

```bash
python -m src.sequential /ruta/a/mx.zip
```

Esta versión lee los registros del ZIP uno por uno, sin extraer los JSON a disco.
