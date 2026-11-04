
import json

import pytest

from cidd.engine.integrations import (
    MAPBOX_PACKAGE,
    MAPBOX_VERSION,
    IntegrationError,
    required_packages,
    allowed_external_imports,
)


def contract(layer="presentation", map_config=None):
    specification = {"name": "TaxiCatMobileView"}
    if map_config is not None:
        specification["map"] = map_config

    return {
        "id": f"{layer}.TaxiCatMobileView",
        "specification": json.dumps(specification),
    }


def test_no_map_requires_no_packages():
    graph = {"contracts": [contract()]}
    assert required_packages(graph) == {}


def test_mapbox_declares_package():
    screen = contract(map_config={
        "provider": "mapbox",
        "token_env": "MAPBOX_ACCESS_TOKEN",
    })

    assert required_packages(
        {"contracts": [screen]}
    ) == {MAPBOX_PACKAGE: MAPBOX_VERSION}


def test_mapbox_import_is_presentation_only():
    config = {
        "provider": "mapbox",
        "token_env": "MAPBOX_ACCESS_TOKEN",
    }

    assert allowed_external_imports(
        contract(map_config=config)
    ) == ("package:mapbox_maps_flutter/",)

    assert allowed_external_imports(
        contract(layer="domain", map_config=config)
    ) == ()


def test_unknown_provider_rejected():
    screen = contract(map_config={
        "provider": "unknown",
        "token_env": "MAPBOX_ACCESS_TOKEN",
    })

    with pytest.raises(IntegrationError):
        required_packages({"contracts": [screen]})


def test_wrong_token_env_rejected():
    screen = contract(map_config={
        "provider": "mapbox",
        "token_env": "SECRET_KEY",
    })

    with pytest.raises(IntegrationError):
        required_packages({"contracts": [screen]})
