"""Promote sanitizable failed worker outputs into a new, auditable generation run.

No LLM, no alteration of the original run, no claim of analyzer validation.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import shutil

from cidd.engine.generation import GenerationError, load_verified_graph
from cidd.engine.selective import verified_snapshot, signature, _source_path
from cidd.engine.sanitizer import sanitize_dart


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _package(project: Path) -> str:
    pubspec = (project / 'pubspec.yaml').read_text(encoding='utf-8')
    match = re.search(r'(?m)^name:\s*([a-z][a-z0-9_]*)\s*(?:#.*)?$', pubspec)
    if not match:
        raise GenerationError('Project pubspec.yaml must declare a valid Dart package name')
    return match.group(1)


def recover(graph_path: Path, run_path: Path, project: Path, output_root: Path,
            *, run_id: str | None = None) -> dict:
    """Recover rejected raw outputs; fail closed if ANY output cannot be recovered."""
    contracts = load_verified_graph(graph_path)
    graph = _load(graph_path)
    if verified_snapshot(run_path)['fingerprint'] != graph['fingerprint']:
        raise GenerationError('Recovery requires identical sealed graph to source run')
    previous = _load(run_path / 'manifest.json')
    prev = {entry['id']: entry for entry in previous['results']}
    if len(prev) != len(previous['results']):
        raise GenerationError('Duplicate contract in source manifest')
    entries = {entry['id']: entry for entry in graph['contracts']}
    package = _package(project)
    run_id = run_id or datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    if not re.fullmatch(r'[A-Za-z0-9_-]+', run_id):
        raise GenerationError('Unsafe run ID')
    destination = output_root / run_id
    destination.mkdir(parents=True, exist_ok=False)
    shutil.copy2(graph_path, destination / 'sealed-graph.json')
    results = []
    for contract in contracts:
        cid = contract.contract_id
        rel = _source_path(cid, contract.language)
        prior = prev.get(cid)
        item = {'id': cid, 'status': 'FAILED', 'decision': 'RECOVERY',
                'contract_hash': signature(entries[cid]), 'input_tokens': 0,
                'output_tokens': 0, 'elapsed_seconds': 0.0}
        try:
            if prior is None:
                raise GenerationError(f'Missing source manifest entry: {cid}')
            if prior.get('contract_hash') and prior['contract_hash'] != item['contract_hash']:
                raise GenerationError(f'Contract signature differs in source manifest: {cid}')
            if prior.get('status') in ('GENERATED', 'REUSED'):
                path = prior.get('path')
                if not isinstance(path, str) or Path(path) != rel:
                    raise GenerationError(f'Unexpected source path for {cid}')
                original = run_path / rel
                data = original.read_bytes()
                if not prior.get('source_sha256') or prior['source_sha256'] != _sha(data):
                    raise GenerationError(f'Missing or mismatched source SHA-256: {cid}')
                item['decision'] = 'REUSED'
                item['origin_path'] = rel.as_posix()
            elif prior.get('status') == 'FAILED':
                raw_relative = prior.get('raw_response_path')
                expected = Path('failed') / rel.parent / (rel.stem + '.raw.txt')
                if raw_relative and Path(raw_relative) != expected:
                    raise GenerationError(f'Unexpected raw response location: {cid}')
                raw_path = run_path / expected
                raw = raw_path.read_text(encoding='utf-8')
                if contract.language.lower() != 'dart':
                    raise GenerationError(f'Unsupported recovery language: {contract.language}')
                cleaned = sanitize_dart(raw, contract_id=cid,
                    dependencies=tuple(d.contract_id for d in contract.dependencies),
                    all_contract_ids=tuple(x.contract_id for x in contracts),
                    package_name=package).source
                if not cleaned.strip() or '```' in cleaned:
                    raise GenerationError(f'Invalid recovered source: {cid}')
                data = cleaned.encode('utf-8')
                item['decision'] = 'RECOVERED'
                item['raw_response_path'] = expected.as_posix()
                item['raw_response_sha256'] = _sha(raw_path.read_bytes())
            else:
                raise GenerationError(f'Unsupported source status for {cid}: {prior.get("status")}')
            dest = destination / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            item.update(status='REUSED', path=rel.as_posix(), source_sha256=_sha(data),
                        origin_run=str(run_path), origin_status=prior.get('status'))
        except Exception as exc:
            item['error'] = f'{type(exc).__name__}: {exc}'
        results.append(item)
    manifest = {'schema': 'cidd.generation-run/0.1', 'graph_fingerprint': graph['fingerprint'],
                'results': results, 'input_tokens': 0, 'output_tokens': 0,
                'token_counts_complete': all(x['status'] != 'FAILED' for x in results),
                'recovery_source': str(run_path), 'validation_status': 'NOT_VALIDATED'}
    (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return {'run_dir': destination, 'manifest': manifest}


def main() -> None:
    parser = argparse.ArgumentParser(description='Offline recovery of failed worker responses')
    parser.add_argument('--graph', required=True, type=Path)
    parser.add_argument('--run', required=True, type=Path)
    parser.add_argument('--project', required=True, type=Path)
    parser.add_argument('--output', type=Path, default=Path('.cidd/generated-runs'))
    args = parser.parse_args()
    result = recover(args.graph, args.run, args.project, args.output)
    for entry in result['manifest']['results']:
        print(entry['status'], entry['id'], entry['decision'], entry.get('error', ''))
    print('New run:', result['run_dir'])
    print('Tokens:', 0)
    if any(x['status'] == 'FAILED' for x in result['manifest']['results']):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
