from src.shuffle_reduce import shuffle, reduce, shuffle_y_reduce


def test_shuffle_agrupa_por_palabra():
    pares = [("hola", 1), ("mundo", 1), ("hola", 1)]
    assert shuffle(pares) == {"hola": [1, 1], "mundo": [1]}


def test_shuffle_lista_vacia():
    assert shuffle([]) == {}


def test_reduce_suma_valores():
    grupos = {"hola": [1, 1], "mundo": [1]}
    assert reduce(grupos) == {"hola": 2, "mundo": 1}


def test_reduce_vacio():
    assert reduce({}) == {}


def test_reduce_valores_distintos_de_uno():
    assert reduce({"a": [3, 2, 5]}) == {"a": 10}


def test_shuffle_y_reduce_ejemplo_del_equipo():
    pares = [("hola", 1), ("mundo", 1), ("hola", 1)]
    assert shuffle_y_reduce(pares) == {"hola": 2, "mundo": 1}


def test_una_sola_palabra_repetida():
    pares = [("a", 1)] * 5
    assert shuffle_y_reduce(pares) == {"a": 5}


def test_no_modifica_la_entrada():
    pares = [("x", 1), ("y", 1)]
    copia = list(pares)
    shuffle_y_reduce(pares)
    assert pares == copia