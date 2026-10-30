"""CIDD validated snapshot v0.1: immutable-ish, content-addressed assembled Dart evidence.

Promote only a successful assembly/analyzer report matching the supplied sealed graph.
Snapshot verification proves file integrity, not that analysis was independently rerun.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path


class SnapshotError(ValueError):
    pass


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def _read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise SnapshotError(f'Cannot read JSON {path}: {exc}') from exc
    if not isinstance(value, dict):
        raise SnapshotError(f'Not a JSON object: {path}')
    return value


def _safe_rel(value: str) -> Path:
    """Accept native Windows/POSIX report paths; store canonical POSIX paths.

    Reject absolute paths, traversal and alternate-drive syntax on every host OS.
    """
    if not isinstance(value, str) or not value or '\x00' in value:
        raise SnapshotError(f'Unsafe relative file path: {value!r}')
    normalized = value.replace('\\', '/')
    parts = normalized.split('/')
    if (normalized.startswith('/') or ':' in normalized or
            any(part in ('', '.', '..') for part in parts) or
            len(parts) < 2 or parts[0] != 'lib' or
            not normalized.endswith('.dart')):
        raise SnapshotError(f'Unsafe relative file path: {value!r}')
    return Path(*parts)


def promote(*, graph_path: Path, assembly: Path, output: Path, source_run: str | None = None) -> dict:
    graph = _read_json(graph_path)
    report = _read_json(assembly / 'cidd-assembly-report.json')
    fingerprint = graph.get('fingerprint')
    if not isinstance(fingerprint, str) or not fingerprint:
        raise SnapshotError('Sealed graph missing fingerprint')
    if report.get('graph_fingerprint') != fingerprint:
        raise SnapshotError('Graph fingerprint does not match assembly report')
    if report.get('analyzer', {}).get('status') != 'PASS':
        raise SnapshotError('Assembly analyzer has not passed')
    if report.get('pub_get', {}).get('status') != 'PASS':
        raise SnapshotError('Dependency resolution has not passed')
    if report.get('bootstrap', {}).get('status') != 'PASS':
        raise SnapshotError('Bootstrap has not passed')
    contracts = graph.get('contracts')
    if not isinstance(contracts, list) or not contracts:
        raise SnapshotError('Sealed graph has no contracts')
    ids = [c['id'] for c in contracts]
    if len(ids) != len(set(ids)):
        raise SnapshotError('Duplicate contract IDs')
    records = report.get('contracts', [])
    if len(records) != len(ids) or {r.get('id') for r in records} != set(ids):
        raise SnapshotError('Assembly report does not cover all graph contracts exactly')
    if any(r.get('status') != 'ASSEMBLED' for r in records):
        raise SnapshotError('At least one contract was not assembled')
    mappings: dict[str, str] = {}
    for record in records:
        rel = _safe_rel(record.get('path'))
        if str(rel).replace('\\', '/') in mappings.values():
            raise SnapshotError('Duplicate source paths')
        if not (assembly / rel).is_file():
            raise SnapshotError(f'Missing assembled source {rel}')
        mappings[record['id']] = rel.as_posix()
    main = assembly / 'lib' / 'main.dart'
    if not main.is_file():
        raise SnapshotError('Missing generated Flutter main.dart')
    if output.exists():
        raise SnapshotError(f'Snapshot destination already exists: {output}')
    # Preserve all Dart files, detecting missing or extra code not represented in graph.
    expected = set(mappings.values()) | {'lib/main.dart'}
    actual = {p.relative_to(assembly).as_posix() for p in (assembly / 'lib').rglob('*.dart')}
    if actual != expected:
        raise SnapshotError(f'Unexpected or missing Dart sources: {sorted(actual ^ expected)}')
    manifest = {
        'schema': 'cidd.validated-snapshot/0.1',
        'graph_fingerprint': fingerprint,
        'package': report.get('package'),
        'validation': {'pub_get': 'PASS', 'bootstrap': 'PASS', 'analyzer': 'PASS',
                       'runtime_tests': 'NOT_VERIFIED'},
        'source_run': source_run,
        'contract_sources': dict(sorted(mappings.items())),
        'files': {rel: _sha(assembly / rel) for rel in sorted(expected)},
        'provenance': {r['id']: {'recovered_from_failed': bool(r.get('recovered_from_failed', False))}
                       for r in records},
        'evidence': {'assembly_report_sha256': _sha(assembly / 'cidd-assembly-report.json'),
                     'sealed_graph_sha256': _sha(graph_path)},
    }
    try:
        for rel in sorted(expected):
            target = output / 'sources' / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(assembly / rel, target)
        evidence = output / 'evidence'
        evidence.mkdir(parents=True)
        shutil.copyfile(graph_path, evidence / 'sealed-graph.json')
        shutil.copyfile(assembly / 'cidd-assembly-report.json', evidence / 'cidd-assembly-report.json')
        (output / 'snapshot.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        verify(output)
    except Exception:
        shutil.rmtree(output, ignore_errors=True)
        raise
    return manifest


def verify(directory: Path, graph_path: Path | None = None) -> dict:
    manifest = _read_json(directory / 'snapshot.json')
    if manifest.get('schema') != 'cidd.validated-snapshot/0.1':
        raise SnapshotError('Unsupported snapshot schema')
    files = manifest.get('files')
    if not isinstance(files, dict) or not files:
        raise SnapshotError('Missing file hashes')
    expected = set(files)
    actual = {p.relative_to(directory / 'sources').as_posix() for p in (directory / 'sources').rglob('*.dart')}
    if actual != expected:
        raise SnapshotError('Snapshot source inventory mismatch')
    for rel, digest in files.items():
        _safe_rel(rel)
        path = directory / 'sources' / rel
        if not path.is_file() or _sha(path) != digest:
            raise SnapshotError(f'Source integrity failure: {rel}')
    evidence = manifest.get('evidence', {})
    for key, filename in (('assembly_report_sha256', 'cidd-assembly-report.json'),
                          ('sealed_graph_sha256', 'sealed-graph.json')):
        path = directory / 'evidence' / filename
        if not path.is_file() or _sha(path) != evidence.get(key):
            raise SnapshotError(f'Evidence integrity failure: {filename}')
    sealed = _read_json(directory / 'evidence' / 'sealed-graph.json')
    report = _read_json(directory / 'evidence' / 'cidd-assembly-report.json')
    if sealed.get('fingerprint') != manifest.get('graph_fingerprint') or report.get('graph_fingerprint') != manifest.get('graph_fingerprint'):
        raise SnapshotError('Fingerprint mismatch')
    if report.get('analyzer', {}).get('status') != 'PASS':
        raise SnapshotError('Analyzer evidence is not PASS')
    if graph_path is not None:
        current = _read_json(graph_path)
        if current.get('fingerprint') != manifest['graph_fingerprint']:
            raise SnapshotError('Current graph fingerprint differs from snapshot')
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description='CIDD validated assembled snapshots (no LLM calls)')
    commands = parser.add_subparsers(dest='action', required=True)
    p = commands.add_parser('promote')
    p.add_argument('--graph', required=True, type=Path)
    p.add_argument('--assembly', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--source-run', default=None)
    v = commands.add_parser('verify')
    v.add_argument('--snapshot', required=True, type=Path)
    v.add_argument('--graph', type=Path)
    args = parser.parse_args()
    try:
        if args.action == 'promote':
            result = promote(graph_path=args.graph, assembly=args.assembly, output=args.output, source_run=args.source_run)
            print(f'PROMOTED {len(result["contract_sources"])} contracts, {len(result["files"])} Dart files')
        else:
            result = verify(args.snapshot, args.graph)
            print(f'VERIFIED {len(result["contract_sources"])} contracts, {len(result["files"])} Dart files')
        print('Graph fingerprint:', result['graph_fingerprint'])
        print('Analyzer evidence:', result['validation']['analyzer'])
        print('Runtime tests:', result['validation']['runtime_tests'])
    except SnapshotError as exc:
        parser.exit(1, f'Snapshot error: {exc}\n')


if __name__ == '__main__':
    main()
