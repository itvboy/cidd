import json
from pathlib import Path

import pytest

from cidd.engine.snapshot import SnapshotError, promote, verify


def fixture(tmp_path: Path):
    graph = tmp_path / 'graph.json'
    graph.write_text(json.dumps({'fingerprint': 'abc123', 'contracts': [
        {'id': 'domain.Todo'}, {'id': 'presentation.TodoView'}]}), encoding='utf-8')
    assembly = tmp_path / 'assembled'
    for rel in ['lib/domain/todo.dart', 'lib/presentation/todo_view.dart', 'lib/main.dart']:
        file = assembly / rel
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text('// ' + rel, encoding='utf-8')
    report = {'graph_fingerprint': 'abc123', 'package': 'todo',
              'contracts': [
                  {'id': 'domain.Todo', 'status': 'ASSEMBLED', 'path': 'lib/domain/todo.dart'},
                  {'id': 'presentation.TodoView', 'status': 'ASSEMBLED',
                   'path': 'lib/presentation/todo_view.dart', 'recovered_from_failed': True}],
              'pub_get': {'status': 'PASS'}, 'bootstrap': {'status': 'PASS'},
              'analyzer': {'status': 'PASS'}}
    (assembly / 'cidd-assembly-report.json').write_text(json.dumps(report), encoding='utf-8')
    return graph, assembly


def test_promote_verify_and_provenance(tmp_path):
    graph, assembly = fixture(tmp_path)
    dest = tmp_path / 'snapshot'
    m = promote(graph_path=graph, assembly=assembly, output=dest, source_run='run001')
    assert len(m['contract_sources']) == 2
    assert len(m['files']) == 3
    assert m['provenance']['presentation.TodoView']['recovered_from_failed'] is True
    assert m['validation']['runtime_tests'] == 'NOT_VERIFIED'
    assert verify(dest, graph)['source_run'] == 'run001'


def test_modified_source_rejected(tmp_path):
    graph, assembly = fixture(tmp_path)
    dest = tmp_path / 'snapshot'
    promote(graph_path=graph, assembly=assembly, output=dest)
    (dest / 'sources/lib/main.dart').write_text('// changed', encoding='utf-8')
    with pytest.raises(SnapshotError, match='integrity'):
        verify(dest)


def test_failed_analyzer_cannot_promote(tmp_path):
    graph, assembly = fixture(tmp_path)
    path = assembly / 'cidd-assembly-report.json'
    report = json.loads(path.read_text())
    report['analyzer']['status'] = 'FAIL'
    path.write_text(json.dumps(report))
    with pytest.raises(SnapshotError, match='analyzer'):
        promote(graph_path=graph, assembly=assembly, output=tmp_path / 'snapshot')


def test_other_graph_rejected(tmp_path):
    graph, assembly = fixture(tmp_path)
    dest = tmp_path / 'snapshot'
    promote(graph_path=graph, assembly=assembly, output=dest)
    graph.write_text(json.dumps({'fingerprint': 'xyz', 'contracts': []}))
    with pytest.raises(SnapshotError, match='fingerprint'):
        verify(dest, graph)


def test_extra_dart_file_rejected(tmp_path):
    graph, assembly = fixture(tmp_path)
    (assembly / 'lib' / 'extra.dart').write_text('// extra')
    with pytest.raises(SnapshotError, match='Unexpected'):
        promote(graph_path=graph, assembly=assembly, output=tmp_path / 'snapshot')


def test_promote_windows_report_paths(tmp_path):
    graph, assembly = fixture(tmp_path)
    report_path = assembly / 'cidd-assembly-report.json'
    report = json.loads(report_path.read_text())
    for rec in report['contracts']:
        rec['path'] = rec['path'].replace('/', chr(92))
    report_path.write_text(json.dumps(report))
    dest = tmp_path / 'snapshot'
    manifest = promote(graph_path=graph, assembly=assembly, output=dest)
    assert manifest['contract_sources']['domain.Todo'] == 'lib/domain/todo.dart'
    assert verify(dest, graph)['contract_sources'] == manifest['contract_sources']


@pytest.mark.parametrize('bad', [
    r'lib\..\secrets.dart', r'C:\temp\code.dart',
    r'\\server\share\code.dart', 'lib//todo.dart',
    'lib/./todo.dart', 'lib/domain/../todo.dart',
])
def test_unsafe_paths_rejected(tmp_path, bad):
    graph, assembly = fixture(tmp_path)
    report_path = assembly / 'cidd-assembly-report.json'
    report = json.loads(report_path.read_text())
    report['contracts'][0]['path'] = bad
    report_path.write_text(json.dumps(report))
    with pytest.raises(SnapshotError, match='Unsafe'):
        promote(graph_path=graph, assembly=assembly, output=tmp_path / 'snapshot')
