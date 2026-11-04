
import json
from pathlib import Path

import pytest

from cidd.engine.integrations import mapbox_configuration


def test_mapbox_configuration_detected():
    screen = {
        "id": "presentation.TaxiCatMobileView",
        "specification": json.dumps({
            "name": "TaxiCatMobileView",
            "map": {
                "provider": "mapbox",
                "token_env": "MAPBOX_ACCESS_TOKEN",
            },
        }),
    }

    config = mapbox_configuration(screen)

    assert config is not None
    assert config["provider"] == "mapbox"


def test_screen_without_mapbox():
    screen = {
        "id": "presentation.TaxiCatMobileView",
        "specification": json.dumps({
            "name": "TaxiCatMobileView",
        }),
    }

    assert mapbox_configuration(screen) is None
