from collections import defaultdict


def shuffle(pares):
    """Agrupa los pares (palabra, valor) por palabra."""
    grupos = defaultdict(list)
    for palabra, valor in pares:
        grupos[palabra].append(valor)
    return dict(grupos)


def reduce(grupos):
    """Suma los valores de cada palabra."""
    return {palabra: sum(valores) for palabra, valores in grupos.items()}


def shuffle_y_reduce(pares):
    """Atajo: agrupa y suma en un solo paso."""
    return reduce(shuffle(pares))