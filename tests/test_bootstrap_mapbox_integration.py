
import copy
import json
from pathlib import Path

from cidd.engine.bootstrap import _bootstrap_flutter_http


GRAPH_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "taxicat_http_graph.json"
)

def generate_main(tmp_path, with_mapbox):
    graph = json.loads(GRAPH_PATH.read_text(encoding="utf-8"))
    graph = copy.deepcopy(graph)

    screen = next(
        contract
        for contract in graph["contracts"]
        if contract["id"] == "presentation.TaxiCatMobileView"
    )

    spec = json.loads(screen["specification"])

    if with_mapbox:
        spec["map"] = {
            "provider": "mapbox",
            "token_env": "MAPBOX_ACCESS_TOKEN",
        }
    else:
        spec.pop("map", None)

    screen["specification"] = json.dumps(spec)

    _bootstrap_flutter_http(
        graph,
        tmp_path,
        "taxicat_mobile",
    )

    return (tmp_path / "lib" / "main.dart").read_text(
        encoding="utf-8"
    )


def test_bootstrap_with_mapbox(tmp_path):
    main = generate_main(tmp_path, with_mapbox=True)

    assert (
        "package:mapbox_maps_flutter/mapbox_maps_flutter.dart"
        in main
    )
    assert "MAPBOX_ACCESS_TOKEN" in main
    assert "MapboxOptions.setAccessToken(mapboxToken);" in main

    # The existing HTTP bootstrap must remain intact.
    assert "TAXICAT_API_URL" in main
    assert "HttpRideRepository(baseUrl)" in main

    for use_case in (
        "RequestRide",
        "ListAvailableRides",
        "GetRideStatus",
        "AcceptRide",
        "StartRide",
        "CompleteRide",
        "CancelRide",
    ):
        assert f"{use_case}(repository)" in main


def test_bootstrap_without_mapbox(tmp_path):
    main = generate_main(tmp_path, with_mapbox=False)

    assert "mapbox_maps_flutter" not in main
    assert "MAPBOX_ACCESS_TOKEN" not in main
    assert "MapboxOptions" not in main

    assert "TAXICAT_API_URL" in main
