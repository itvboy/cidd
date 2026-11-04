
import json

import pytest

from cidd.engine.assembly import _prepare_dependencies
from cidd.engine.integrations import IntegrationError


def make_graph(map_config=None):
    specification = {"name": "TaxiCatMobileView"}

    if map_config is not None:
        specification["map"] = map_config

    return {
        "contracts": [
            {
                "id": "presentation.TaxiCatMobileView",
                "specification": json.dumps(specification),
            }
        ]
    }


def make_project(tmp_path, pubspec):
    tmp_path.joinpath("pubspec.yaml").write_text(
        pubspec,
        encoding="utf-8",
    )
    return tmp_path


MAPBOX = {
    "provider": "mapbox",
    "token_env": "MAPBOX_ACCESS_TOKEN",
}


def test_mapbox_dependency_added(tmp_path):
    project = make_project(
        tmp_path,
        "name: taxicat_mobile\ndependencies:\n"
        "  flutter:\n    sdk: flutter\n",
    )

    _prepare_dependencies(make_graph(MAPBOX), project)

    result = (project / "pubspec.yaml").read_text(
        encoding="utf-8"
    )

    assert "mapbox_maps_flutter: ^3.34.1" in result


def test_no_mapbox_dependency_without_integration(tmp_path):
    project = make_project(
        tmp_path,
        "name: taxicat_mobile\ndependencies:\n"
        "  flutter:\n    sdk: flutter\n",
    )

    _prepare_dependencies(make_graph(), project)

    result = (project / "pubspec.yaml").read_text(
        encoding="utf-8"
    )

    assert "mapbox_maps_flutter:" not in result


def test_mapbox_dependency_not_duplicated(tmp_path):
    project = make_project(
        tmp_path,
        "name: taxicat_mobile\ndependencies:\n"
        "  mapbox_maps_flutter: ^3.34.1\n",
    )

    _prepare_dependencies(make_graph(MAPBOX), project)

    result = (project / "pubspec.yaml").read_text(
        encoding="utf-8"
    )

    assert result.count("mapbox_maps_flutter:") == 1


def test_unknown_map_provider_rejected(tmp_path):
    project = make_project(
        tmp_path,
        "name: taxicat_mobile\ndependencies:\n",
    )

    graph = make_graph({
        "provider": "unknown",
        "token_env": "MAPBOX_ACCESS_TOKEN",
    })

    with pytest.raises(IntegrationError):
        _prepare_dependencies(graph, project)
