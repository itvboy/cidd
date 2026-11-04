import json

import pytest

from cidd.contracts.expander import _extract_interface
from cidd.genome.parser import GenomeError


def test_rejects_async_repository_interface():
    interface = (
        "abstract class TodoRepository {\n"
        "  Future<List<Todo>> findAll();\n"
        "}"
    )

    with pytest.raises(GenomeError, match="synchronous"):
        _extract_interface(
            json.dumps({"interface": interface}),
            "TodoRepository",
        )


def test_accepts_sync_repository_interface():
    interface = (
        "abstract class TodoRepository {\n"
        "  List<Todo> findAll();\n"
        "}"
    )

    result = _extract_interface(
        json.dumps({"interface": interface}),
        "TodoRepository",
    )

    assert result == interface