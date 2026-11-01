
from copy import deepcopy

import pytest

from cidd.contracts.materializer import build_graph
from cidd.genome.parser import GenomeError


def genome():
    return {
        "genome": "0.1",
        "project": {
            "name": "todo_plus",
            "template": "flutter",
            "language": "dart",
        },
        "domain": {"entities": []},
        "application": {"use_cases": []},
        "infrastructure": {"persistence": []},
        "presentation": {
            "framework": "flutter",
            "entry_screen": "SplashScreen",
            "assets": [
                {
                    "path": "assets/images/cidd_logo.png",
                    "type": "image",
                }
            ],
            "screens": [
                {
                    "name": "SplashScreen",
                    "image": "assets/images/cidd_logo.png",
                    "navigation": {
                        "on_start": {
                            "to": "TodoView",
                            "delay_ms": 2000,
                        }
                    },
                },
                {"name": "TodoView"},
            ],
        },
    }


def test_presentation_metadata_is_sealed():
    graph = build_graph(genome()).to_dict()

    assert graph["presentation"]["entry_screen"] == "SplashScreen"
    assert graph["presentation"]["assets"][0]["path"] == (
        "assets/images/cidd_logo.png"
    )


def test_entry_screen_changes_fingerprint():
    original = genome()
    modified = deepcopy(original)
    modified["presentation"]["entry_screen"] = "TodoView"

    assert (
        build_graph(original).fingerprint
        != build_graph(modified).fingerprint
    )


def test_unknown_navigation_target_is_rejected():
    data = genome()
    data["presentation"]["screens"][0]["navigation"]["on_start"]["to"] = (
        "MissingView"
    )

    with pytest.raises(GenomeError):
        build_graph(data)
