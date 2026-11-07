from pathlib import Path
from typing import Any, Iterator
from zipfile import ZipFile

import ijson


def iter_records(zip_path: str | Path) -> Iterator[dict[str, Any]]:
    """Yield JSON records from every .json file in a ZIP archive."""
    archive_path = Path(zip_path)
    if not archive_path.is_file():
        raise FileNotFoundError(f"No se encontró el archivo: {archive_path}")

    with ZipFile(archive_path) as archive:
        json_members = sorted(
            name for name in archive.namelist() if name.lower().endswith(".json")
        )
        if not json_members:
            raise ValueError(f"El ZIP no contiene archivos JSON: {archive_path}")

        for member in json_members:
            with archive.open(member) as source:
                for index, record in enumerate(ijson.items(source, "item"), start=1):
                    if not isinstance(record, dict):
                        raise ValueError(
                            f"Registro inválido en {member}, elemento {index}: "
                            "se esperaba un objeto JSON"
                        )
                    yield record
