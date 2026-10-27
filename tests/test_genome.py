import pytest

from cidd.genome.parser import GenomeError
from cidd.genome.validator import validate_genome


def valid_genome():
    return {
        "genome": "0.1",
        "project": {
            "name": "todo",
            "template": "flutter",
        },
        "domain": {"entities": []},
        "application": {"use_cases": []},
        "infrastructure": {"persistence": []},
        "presentation": {
            "framework": "flutter",
            "screens": [],
        },
    }


def test_valid_genome():
    validate_genome(valid_genome())


def test_unsupported_version():
    genome = valid_genome()
    genome["genome"] = "0.2"

    with pytest.raises(
        GenomeError,
        match="Unsupported genome version",
    ):
        validate_genome(genome)


def test_invalid_section_order():
    genome = valid_genome()

    application = genome.pop("application")
    genome["application"] = application

    with pytest.raises(
        GenomeError,
        match="Invalid genome sections or order",
    ):
        validate_genome(genome)