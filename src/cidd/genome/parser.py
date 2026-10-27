
from pathlib import Path

import yaml


class GenomeError(Exception):
    pass


def load_genome(path: Path) -> dict:
    if not path.is_file():
        raise GenomeError(f"Genome not found: {path}")

    try:
        with path.open("r", encoding="utf-8") as file:
            genome = yaml.safe_load(file)
    except yaml.YAMLError as error:
        raise GenomeError(
            f"Invalid YAML syntax: {error}"
        ) from error

    if not isinstance(genome, dict):
        raise GenomeError(
            "Genome root must be a YAML mapping"
        )

    return genome
