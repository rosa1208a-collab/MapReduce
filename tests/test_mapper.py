import unittest

from src.mapper import map_record


class MapperTests(unittest.TestCase):

    # Comprobar palabras simples
    def test_palabras_simples(self):
        record = {"id": 1, "text": "Hola mundo"}

        resultado = map_record(record)

        esperado = [("hola", 1), ("mundo", 1)]

        self.assertEqual(resultado, esperado)

    # Comprobar palabras repetidas
    def test_palabras_repetidas(self):
        record = {"id": 2, "text": "Hola hola mundo"}

        resultado = map_record(record)

        esperado = [
            ("hola", 1),
            ("hola", 1),
            ("mundo", 1)
        ]

        self.assertEqual(resultado, esperado)

    # Comprobar mayúsculas y minúsculas
    def test_mayusculas(self):
        record = {"id": 3, "text": "HOLA Mundo"}

        resultado = map_record(record)

        esperado = [("hola", 1), ("mundo", 1)]

        self.assertEqual(resultado, esperado)

    # Comprobar palabras con acentos
    def test_palabras_con_acentos(self):
        record = {"id": 4, "text": "México Querétaro"}

        resultado = map_record(record)

        esperado = [("méxico", 1), ("querétaro", 1)]

        self.assertEqual(resultado, esperado)

    # Comprobar signos de puntuación y números
    def test_signos_y_numeros(self):
        record = {"id": 5, "text": "¡Hola, mundo! 2026"}

        resultado = map_record(record)

        esperado = [("hola", 1), ("mundo", 1)]

        self.assertEqual(resultado, esperado)

    # Comprobar texto vacío
    def test_texto_vacio(self):
        record = {"id": 6, "text": ""}

        resultado = map_record(record)

        self.assertEqual(resultado, [])

    # Comprobar registros inválidos
    def test_texto_invalido(self):
        record = {"id": 7, "text": None}

        with self.assertRaises(ValueError):
            map_record(record)


if __name__ == "__main__":
    unittest.main()
