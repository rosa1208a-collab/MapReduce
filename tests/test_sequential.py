import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from src.sequential import count_words_sequential, words_in_text


class SequentialWordCountTests(unittest.TestCase):
    def test_normalizes_case_and_ignores_punctuation_and_numbers(self) -> None:
        self.assertEqual(
            words_in_text("¡Hola, HOLA mundo! México 2026"),
            ["hola", "hola", "mundo", "méxico"],
        )

    def test_counts_words_from_json_records_in_zip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            zip_path = Path(directory) / "sample.zip"
            records = [
                {"id": 1, "text": "Hola, hola mundo."},
                {"id": 2, "text": "Mundo de México."},
            ]
            with ZipFile(zip_path, "w") as archive:
                archive.writestr(
                    "mx_1.json",
                    json.dumps(records, ensure_ascii=False),
                )

            counts = count_words_sequential(zip_path)

        self.assertEqual(
            counts,
            {"hola": 2, "mundo": 2, "de": 1, "méxico": 1},
        )


if __name__ == "__main__":
    unittest.main()
