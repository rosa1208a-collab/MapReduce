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
- Convertir palabras a minúsculas.
- Ignorar signos de puntuación.
- Mostrar las 20 palabras más frecuentes.
