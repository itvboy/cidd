import pytest

from cidd.contracts.materializer import _dart_value_type
from cidd.genome.parser import GenomeError


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("list<Ride>", "List<Ride>"),
        ("List<Ride>", "List<Ride>"),
        ("List<int>", "List<int>"),
        ("List<string>", "List<String>"),
    ],
)
def test_supported_list_types(raw, expected):
    assert _dart_value_type(
        raw,
        {"Ride"},
        "test.output",
    ) == expected


def test_unknown_list_element_is_rejected():
    with pytest.raises(GenomeError):
        _dart_value_type(
            "List<Unknown>",
            {"Ride"},
            "test.output",
        )