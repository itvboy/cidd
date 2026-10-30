from copy import deepcopy
import json
import pytest
from cidd.contracts.materializer import build_graph
from cidd.genome.parser import GenomeError


def genome():
    return {
        'genome': '0.1',
        'project': {'name': 'todo', 'template': 'flutter', 'language': 'dart'},
        'domain': {'entities': [{'name': 'Todo', 'fields': [
            {'name': 'id', 'type': 'int', 'nullable': True},
            {'name': 'title', 'type': 'string', 'required': True},
            {'name': 'completed', 'type': 'bool', 'default': False},
        ]}]},
        'application': {'use_cases': [{'name': 'CompleteTodo', 'depends_on': ['domain.Todo']}]},
        'infrastructure': {'persistence': []},
        'presentation': {'framework': 'flutter', 'screens': []},
    }


def test_derives_interface_without_mutating_genome():
    source = genome()
    original = deepcopy(source)
    graph = build_graph(source)
    assert source == original
    case = next(c for c in graph.contracts if c.contract_id == 'application.CompleteTodo')
    entity = next(c for c in graph.contracts if c.contract_id == 'domain.Todo')
    expected = (
        "class Todo {\n"
        "  final int? id;\n"
        "  final String title;\n"
        "  final bool completed;\n"
        "  Todo({this.id, required this.title, this.completed = false});\n"
        "}"
    )
    assert case.dependencies[0].interface == expected
    assert json.loads(entity.specification)['interface'] == expected


def test_invalid_entity_type_fails_closed():
    source = genome()
    source['domain']['entities'][0]['fields'][0]['type'] = 'unrecognized'
    with pytest.raises(GenomeError, match='unsupported Dart type'):
        build_graph(source)


def test_explicit_disagreement_rejected():
    source = genome()
    source['domain']['entities'][0]['interface'] = 'class Todo { }'
    with pytest.raises(GenomeError, match='disagrees'):
        build_graph(source)


def test_fingerprint_reproducible():
    assert build_graph(genome()).fingerprint == build_graph(genome()).fingerprint
