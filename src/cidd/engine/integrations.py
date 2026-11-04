
"""Deterministic external SDK integration registry."""

from __future__ import annotations

import json

MAPBOX_PACKAGE = "mapbox_maps_flutter"
MAPBOX_VERSION = "^3.34.1"
MAPBOX_IMPORT = "package:mapbox_maps_flutter/"


class IntegrationError(ValueError):
    pass


def mapbox_configuration(contract: dict) -> dict | None:
    if not contract["id"].startswith("presentation."):
        return None

    try:
        specification = json.loads(contract["specification"])
    except (ValueError, TypeError, KeyError) as exc:
        raise IntegrationError(
            "Invalid presentation specification"
        ) from exc

    config = specification.get("map")

    if config is None:
        return None

    if not isinstance(config, dict):
        raise IntegrationError("map must be an object")

    if config.get("provider") != "mapbox":
        raise IntegrationError("Unsupported map provider")

    if config.get("token_env") != "MAPBOX_ACCESS_TOKEN":
        raise IntegrationError("Unsupported Mapbox token variable")

    return config


def required_packages(graph: dict) -> dict[str, str]:
    packages = {}

    for contract in graph["contracts"]:
        if mapbox_configuration(contract) is not None:
            packages[MAPBOX_PACKAGE] = MAPBOX_VERSION

    return packages


def allowed_external_imports(contract: dict) -> tuple[str, ...]:
    if mapbox_configuration(contract) is not None:
        return (MAPBOX_IMPORT,)

    return ()
