import re

# Expresión regular para identificar palabras.
# Conserva letras acentuadas e ignora números y signos.
WORD_PATTERN = re.compile(r"[^\W\d_]+", re.UNICODE)


def map_record(record: dict) -> list[tuple[str, int]]:
    """
    Recibe un registro JSON y convierte su texto
    en pares (palabra, 1).
    """

    # Obtener el texto del registro
    text = record.get("text")

    # Verificar que el texto sea válido
    if not isinstance(text, str):
        raise ValueError(
            f"El registro {record.get('id', '(sin id)')} no tiene texto válido"
        )

    # Convertir el texto a minúsculas y separar las palabras
    words = WORD_PATTERN.findall(text.casefold())

    # Crear un par por cada palabra
    pairs = [(word, 1) for word in words]

    return pairs
