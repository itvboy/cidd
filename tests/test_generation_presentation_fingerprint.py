
import json
from pathlib import Path

import pytest

from cidd.contracts.materializer import build_graph, write_graph
from cidd.engine.generation import (
    GenerationError,
    load_verified_graph,
)


def test_multiscreen_graph_fingerprint(tmp_path: Path):
    genome = {
        "genome": "0.1",
        "project": {
            "name": "fingerprint_test",
            "template": "flutter",
            "language": "dart",
        },
        "domain": {"entities": []},
        "application": {"use_cases": []},
        "infrastructure": {"persistence": []},
        "presentation": {
            "framework": "flutter",
            "entry_screen": "HomeView",
            "screens": [
                {
                    "name": "HomeView",
                    "title": "Home",
                    "description": "A simple home screen.",
                    "widgets": ["HomeContent"],
                    "depends_on": [],
                },
                {
                    "name": "AboutView",
                    "title": "About",
                    "description": "A simple about screen.",
                    "widgets": ["AboutContent"],
                    "depends_on": [],
                },
            ],
        },
    }

    graph = build_graph(genome)
    target = tmp_path / "graph.json"

    write_graph(graph, target)

    # The untouched graph must pass verification.
    contracts = load_verified_graph(target)

    assert len(contracts) == 2
    assert graph.presentation is not None

    # Tampering with navigation metadata must invalidate the seal.
    data = json.loads(target.read_text(encoding="utf-8"))
    data["presentation"]["entry_screen"] = "AboutView"

    target.write_text(
        json.dumps(data, ensure_ascii=False),
        encoding="utf-8",
    )

    with pytest.raises(
        GenerationError,
        match="[Ff]ingerprint mismatch",
    ):
        load_verified_graph(target)
