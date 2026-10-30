import json
import pytest
from cidd.contracts.materializer import build_graph, write_graph
from cidd.genome.parser import GenomeError


def genome():
    return {"genome":"0.1", "project":{"name":"taxi", "template":"flutter", "language": "dart"},
            "domain":{"entities":[{"name":"Ride", "language":"python",
                                   "interface":"class Ride: ...", "fields":{"id":"int"}}]},
            "application":{"use_cases":[{"name":"StartRide", "language":"python",
                                      "depends_on":["domain.Ride"], "behavior":"Start ride"}]},
            "infrastructure":{"persistence":[]},
            "presentation":{"framework":"flutter", "screens":[]}}


def test_graph_seals_dependency_interface():
    graph = build_graph(genome())
    assert len(graph.contracts) == 2
    start = next(c for c in graph.contracts if c.contract_id == "application.StartRide")
    assert start.dependencies[0].contract_id == 'domain.Ride'
    assert start.dependencies[0].interface == 'class Ride: ...'
    assert graph.fingerprint == build_graph(genome()).fingerprint


def test_bad_dependency_fails_before_write():
    obj = genome()
    obj['application']['use_cases'][0]['depends_on'] = ['domain.Missing']
    with pytest.raises(GenomeError, match='unknown dependency'):
        build_graph(obj)


def test_missing_dependency_interface_fails():
    obj = genome()
    del obj['domain']['entities'][0]['interface']
    with pytest.raises(GenomeError, match='requires a nonempty interface'):
        build_graph(obj)


def test_write_and_empty_graph(tmp_path):
    obj = genome()
    obj['domain']['entities'] = []
    obj['application']['use_cases'] = []
    graph = build_graph(obj)
    assert graph.contracts == ()
    target = tmp_path / '.cidd' / 'contract-graph.json'
    write_graph(graph, target)
    assert json.loads(target.read_text())['contracts'] == []


def test_duplicate_ids():
    obj = genome()
    obj['domain']['entities'].append(obj['domain']['entities'][0].copy())
    with pytest.raises(GenomeError, match='Duplicate contract'):
        build_graph(obj)
