import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from itertools import islice
from pathlib import Path
from typing import Any, Iterable, Iterator
from zipfile import ZipFile

import ijson

from src.reader import iter_records
from src.sequential import count_words_sequential, words_in_text

# Intentar importar map_record si existe en la rama integrada;
# de lo contrario, definir una versión compatible con la convención del proyecto.
try:
    from src.mapper import map_record  # type: ignore[import-not-found]
except ImportError:
    def map_record(record: dict[str, Any]) -> list[tuple[str, int]]:
        """Convierte el texto de un registro en pares (palabra, 1)."""
        text = record.get("text")
        if not isinstance(text, str):
            raise ValueError(
                f"El registro {record.get('id', '(sin id)')} no tiene texto válido"
            )
        return [(word, 1) for word in words_in_text(text)]

# Intentar importar reduce_pairs si existe en la rama integrada.
try:
    from src.reducer import reduce_pairs  # type: ignore[import-not-found]
except ImportError:
    def reduce_pairs(pairs: Iterable[tuple[str, int]]) -> Counter[str]:
        """Agrupa pares (palabra, conteo) y suma sus valores."""
        counts: Counter[str] = Counter()
        for word, value in pairs:
            counts[word] += value
        return counts


def list_json_members(zip_path: str | Path) -> list[str]:
    """Devuelve la lista ordenada de archivos .json dentro del archivo ZIP."""
    archive_path = Path(zip_path)
    if not archive_path.is_file():
        raise FileNotFoundError(f"No se encontró el archivo: {archive_path}")

    with ZipFile(archive_path) as archive:
        json_members = sorted(
            name for name in archive.namelist() if name.lower().endswith(".json")
        )
        if not json_members:
            raise ValueError(f"El ZIP no contiene archivos JSON: {archive_path}")
    return json_members


def _iter_batches(
    iterator: Iterator[dict[str, Any]], batch_size: int
) -> Iterator[list[dict[str, Any]]]:
    """Agrupa un iterador de registros en lotes de tamaño fijo `batch_size`."""
    while True:
        batch = list(islice(iterator, batch_size))
        if not batch:
            break
        yield batch


def process_records_batch(records: list[dict[str, Any]]) -> Counter[str]:
    """
    Procesa un lote de registros en un proceso trabajador (worker),
    combinando los conteos locales de palabras.
    """
    local_counts: Counter[str] = Counter()
    for record in records:
        text = record.get("text")
        if not isinstance(text, str):
            raise ValueError(
                f"El registro {record.get('id', '(sin id)')} no tiene texto válido"
            )
        local_counts.update(words_in_text(text))
    return local_counts


def process_zip_member(args: tuple[str, str]) -> Counter[str]:
    """
    Procesa un miembro JSON completo dentro del archivo ZIP en un proceso trabajador.
    Permite paralelizar la descompresión, el parseo streaming con ijson y el conteo.
    """
    zip_path_str, member = args
    local_counts: Counter[str] = Counter()
    with ZipFile(zip_path_str) as archive:
        with archive.open(member) as source:
            for index, record in enumerate(ijson.items(source, "item"), start=1):
                if not isinstance(record, dict):
                    raise ValueError(
                        f"Registro inválido en {member}, elemento {index}: "
                        "se esperaba un objeto JSON"
                    )
                text = record.get("text")
                if not isinstance(text, str):
                    raise ValueError(
                        f"El registro {record.get('id', '(sin id)')} no tiene texto válido"
                    )
                local_counts.update(words_in_text(text))
    return local_counts


def combine_counts(partial_counts: Iterable[Counter[str]]) -> Counter[str]:
    """Combina una colección de conteos parciales en un único Counter total."""
    total_counts: Counter[str] = Counter()
    for partial in partial_counts:
        total_counts.update(partial)
    return total_counts


def count_words_parallel(
    zip_path: str | Path,
    workers: int = 4,
    batch_size: int = 1000,
    strategy: str = "auto",
) -> Counter[str]:
    """
    Cuenta las palabras del campo `text` en los archivos JSON dentro de `zip_path`
    en paralelo usando `concurrent.futures.ProcessPoolExecutor`.

    Parámetros:
    - zip_path: Ruta al archivo ZIP.
    - workers: Número de procesos trabajadores (>= 1).
    - batch_size: Tamaño de lote cuando se reparte por lotes de registros.
    - strategy:
        - "auto": Si el ZIP tiene al menos tantos miembros JSON como `workers` (y > 1),
          distribuye por miembro JSON para paralelizar también la lectura/parseo;
          de lo contrario, distribuye por lotes de registros (`batches`).
        - "members": Distribuye un miembro JSON por tarea.
        - "batches": Lee en streaming y envía lotes de `batch_size` registros a los procesos.
    """
    if workers < 1:
        raise ValueError("El número de procesos (workers) debe ser al menos 1")
    if batch_size < 1:
        raise ValueError("El tamaño de lote (batch_size) debe ser al menos 1")
    if strategy not in {"auto", "members", "batches"}:
        raise ValueError("La estrategia debe ser 'auto', 'members' o 'batches'")

    archive_path = Path(zip_path)
    members = list_json_members(archive_path)

    use_members = strategy == "members" or (
        strategy == "auto" and len(members) >= workers and len(members) > 1
    )

    with ProcessPoolExecutor(max_workers=workers) as executor:
        if use_members:
            tasks = [(str(archive_path), member) for member in members]
            partial_results = executor.map(process_zip_member, tasks)
            return combine_counts(partial_results)
        else:
            batches = _iter_batches(iter_records(archive_path), batch_size)
            partial_results = executor.map(process_records_batch, batches)
            return combine_counts(partial_results)


def verify_against_sequential(
    zip_path: str | Path,
    workers: int = 4,
    batch_size: int = 1000,
) -> tuple[bool, Counter[str], Counter[str]]:
    """
    Ejecuta el conteo secuencial y el conteo paralelo con `concurrent.futures`
    y verifica que ambos produzcan exactamente el mismo resultado.
    """
    seq_counts = count_words_sequential(zip_path)
    par_counts = count_words_parallel(
        zip_path, workers=workers, batch_size=batch_size
    )
    return (seq_counts == par_counts), seq_counts, par_counts


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Cuenta palabras del campo text en archivos JSON dentro de un ZIP "
            "usando concurrent.futures.ProcessPoolExecutor."
        )
    )
    parser.add_argument("zip_path", type=Path, help="Ruta al ZIP del dataset")
    parser.add_argument(
        "--workers",
        "-w",
        type=int,
        default=4,
        help="Número de procesos paralelos (predeterminado: 4)",
    )
    parser.add_argument(
        "--batch-size",
        "-b",
        type=int,
        default=1000,
        help="Tamaño de lote de registros para reparto por lotes (predeterminado: 1000)",
    )
    parser.add_argument(
        "--strategy",
        choices=["auto", "members", "batches"],
        default="auto",
        help="Estrategia de partición del trabajo (predeterminado: auto)",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=20,
        help="Cantidad de palabras más frecuentes que se mostrarán (predeterminado: 20)",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Comprobar que el resultado paralelo coincida exactamente con la versión secuencial",
    )
    args = parser.parse_args()

    if args.top < 1:
        parser.error("--top debe ser mayor que cero")
    if args.workers < 1:
        parser.error("--workers debe ser mayor que cero")
    if args.batch_size < 1:
        parser.error("--batch-size debe ser mayor que cero")

    if args.verify:
        matches, seq_counts, par_counts = verify_against_sequential(
            args.zip_path, workers=args.workers, batch_size=args.batch_size
        )
        if not matches:
            raise AssertionError(
                "El resultado paralelo NO coincide con la versión secuencial."
            )
        print(
            f"[OK] Verificación exitosa: el conteo paralelo ({args.workers} procesos) "
            f"coincide exactamente con la versión secuencial "
            f"({len(par_counts)} palabras únicas, {sum(par_counts.values())} totales)."
        )
        counts = par_counts
    else:
        counts = count_words_parallel(
            args.zip_path,
            workers=args.workers,
            batch_size=args.batch_size,
            strategy=args.strategy,
        )

    for word, frequency in counts.most_common(args.top):
        print(f"{word}\t{frequency}")


if __name__ == "__main__":
    main()
