import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from zipfile import ZipFile

from src.parallel_futures import (
    combine_counts,
    count_words_parallel,
    process_records_batch,
    verify_against_sequential,
)
from src.sequential import count_words_sequential


class ParallelFuturesWordCountTests(unittest.TestCase):
    def _create_sample_zip(self, directory: str, num_files: int = 4) -> Path:
        zip_path = Path(directory) / "sample_mx.zip"
        sample_texts = [
            "¡Hola, hola mundo! México lindo y querido 2026.",
            "Querétaro, Ciudad de México, Guadalajara y Monterrey son ciudades de México.",
            "El cómputo de alto rendimiento permite procesar datos en paralelo con Python.",
            "MapReduce divide el problema en fases de Map y Reduce para contar palabras.",
            "La programación paralela mejora el tiempo de ejecución y mide el speedup.",
        ]
        with ZipFile(zip_path, "w") as archive:
            for file_idx in range(1, num_files + 1):
                records = [
                    {
                        "id": (file_idx - 1) * 10 + i + 1,
                        "text": sample_texts[(file_idx + i) % len(sample_texts)],
                    }
                    for i in range(10)
                ]
                archive.writestr(
                    f"mx_{file_idx}.json",
                    json.dumps(records, ensure_ascii=False),
                )
        return zip_path

    def test_combine_counts_merges_partial_counters(self) -> None:
        partials = [
            Counter({"hola": 2, "mundo": 1}),
            Counter({"hola": 3, "méxico": 4}),
            Counter({"mundo": 2}),
        ]
        combined = combine_counts(partials)
        self.assertEqual(combined, Counter({"hola": 5, "méxico": 4, "mundo": 3}))

    def test_process_records_batch_counts_words_correctly(self) -> None:
        batch = [
            {"id": 1, "text": "Hola mundo"},
            {"id": 2, "text": "¡HOLA México 2026!"},
        ]
        result = process_records_batch(batch)
        self.assertEqual(result, Counter({"hola": 2, "mundo": 1, "méxico": 1}))

    def test_parallel_matches_sequential_across_worker_counts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            zip_path = self._create_sample_zip(directory, num_files=8)
            expected = count_words_sequential(zip_path)

            for workers in (1, 2, 4, 8):
                with self.subTest(workers=workers):
                    actual_members = count_words_parallel(
                        zip_path, workers=workers, strategy="members"
                    )
                    self.assertEqual(actual_members, expected)

                    actual_batches = count_words_parallel(
                        zip_path, workers=workers, batch_size=5, strategy="batches"
                    )
                    self.assertEqual(actual_batches, expected)

    def test_verify_against_sequential_returns_true(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            zip_path = self._create_sample_zip(directory, num_files=4)
            matches, seq_counts, par_counts = verify_against_sequential(
                zip_path, workers=2, batch_size=4
            )
            self.assertTrue(matches)
            self.assertEqual(seq_counts, par_counts)

    def test_invalid_arguments_raise_value_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            zip_path = self._create_sample_zip(directory, num_files=1)
            with self.assertRaises(ValueError):
                count_words_parallel(zip_path, workers=0)
            with self.assertRaises(ValueError):
                count_words_parallel(zip_path, workers=2, batch_size=0)
            with self.assertRaises(ValueError):
                count_words_parallel(zip_path, workers=2, strategy="invalid")


if __name__ == "__main__":
    unittest.main()
