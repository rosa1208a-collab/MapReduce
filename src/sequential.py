import argparse
import re
from collections import Counter
from pathlib import Path

from src.reader import iter_records

WORD_PATTERN = re.compile(r"[^\W\d_]+", re.UNICODE)


def words_in_text(text: str) -> list[str]:
    """Return lowercase alphabetic words, including Spanish accented letters."""
    return WORD_PATTERN.findall(text.casefold())


def count_words_sequential(zip_path: str | Path) -> Counter[str]:
    counts: Counter[str] = Counter()
    for record in iter_records(zip_path):
        text = record.get("text")
        if not isinstance(text, str):
            raise ValueError(
                f"El registro {record.get('id', '(sin id)')} no tiene texto válido"
            )
        counts.update(words_in_text(text))
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Cuenta palabras del campo text en archivos JSON dentro de un ZIP."
    )
    parser.add_argument("zip_path", type=Path, help="Ruta al ZIP del dataset")
    parser.add_argument(
        "--top",
        type=int,
        default=20,
        help="Cantidad de palabras más frecuentes que se mostrarán (predeterminado: 20)",
    )
    args = parser.parse_args()
    if args.top < 1:
        parser.error("--top debe ser mayor que cero")

    counts = count_words_sequential(args.zip_path)
    for word, frequency in counts.most_common(args.top):
        print(f"{word}\t{frequency}")


if __name__ == "__main__":
    main()
