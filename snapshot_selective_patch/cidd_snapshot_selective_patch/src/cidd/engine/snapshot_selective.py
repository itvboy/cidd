"""Use a verified assembled snapshot as baseline for CIDD selective generation.

The adapter makes a temporary, provenance-checked generation-run baseline and
passes it to the existing SelectiveEngine. No model calls occur for UNCHANGED
contracts. Changed/new contracts use the normal SelectiveEngine worker path.

CLI: python -m cidd.engine.snapshot_selective --graph GRAPH --snapshot SNAPSHOT
     --output OUTPUT_ROOT [--model MODEL]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

from cidd.engine.generation import GenerationError, load_verified_graph
from cidd.engine.selective import _source_path, selective_generate, signature
from cidd.engine.snapshot import SnapshotError, verify
from cidd.providers.factory import create_provider


def generate_from_snapshot(graph_path: Path, snapshot_dir: Path, output_root: Path,
                           provider, *, run_id: str | None = None) -> dict:
    """Verify snapshot provenance before selective reuse; return run report.

    For evolved graphs, per-contract worker-visible signatures control reuse.
    Snapshot files must match the *historical* sealed graph, not merely the
    current graph's fingerprint.
    """
    graph_path = Path(graph_path)
    snapshot_dir = Path(snapshot_dir)
    output_root = Path(output_root)
    # Validate current graph independently; verification of snapshot checks its
    # own embedded sealed graph and source file hashes.
    load_verified_graph(graph_path)
    manifest = verify(snapshot_dir)
    historical_graph = json.loads((snapshot_dir / 'evidence' / 'sealed-graph.json').read_text(encoding='utf-8'))
    historical = {c['id']: c for c in historical_graph['contracts']}
    sources = manifest['contract_sources']
    if set(sources) != set(historical):
        raise SnapshotError('Snapshot contract inventory differs from sealed graph')
    if set(manifest['files']) != set(sources.values()) | {'lib/main.dart'}:
        raise SnapshotError('Snapshot has unexpected source inventory')

    with tempfile.TemporaryDirectory(prefix='cidd-snapshot-baseline-') as temp:
        baseline = Path(temp)
        shutil.copyfile(snapshot_dir / 'evidence' / 'sealed-graph.json', baseline / 'sealed-graph.json')
        results = []
        for cid, original in sorted(historical.items()):
            rel = sources[cid]
            expected_rel = _source_path(cid, original['language'])
            src = snapshot_dir / 'sources' / rel
            if not src.is_file():
                raise SnapshotError(f'Missing snapshot code for {cid}')
            target = baseline / expected_rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, target)
            payload = target.read_bytes()
            results.append({'id': cid, 'path': expected_rel.as_posix(),
                            'status': 'GENERATED', 'contract_hash': signature(original),
                            'source_sha256': hashlib.sha256(payload).hexdigest(),
                            'input_tokens': 0, 'output_tokens': 0})
        historical_manifest = {'schema': 'cidd.generation-run/0.1',
                               'graph_fingerprint': historical_graph['fingerprint'],
                               'results': results, 'input_tokens': 0,
                               'output_tokens': 0, 'token_counts_complete': True}
        (baseline / 'manifest.json').write_text(
            json.dumps(historical_manifest, sort_keys=True, indent=2) + '\n', encoding='utf-8')
        result = selective_generate(graph_path, baseline, output_root, provider, run_id=run_id)

    # Replace ephemeral-baseline provenance in the run manifest with stable
    # source references, and persist the verified snapshot identity.
    new_dir = Path(result['run_dir'])
    for entry in result['results']:
        if entry['status'] == 'REUSED':
            entry['origin_run'] = f'snapshot:{snapshot_dir.name}'
            entry['origin_path'] = sources[entry['id']]
    result['source_snapshot'] = str(snapshot_dir.resolve())
    result['source_snapshot_fingerprint'] = manifest['graph_fingerprint']
    result['source_snapshot_manifest_sha256'] = hashlib.sha256(
        (snapshot_dir / 'snapshot.json').read_bytes()).hexdigest()
    stored = {k: v for k, v in result.items() if k != 'run_dir'}
    (new_dir / 'manifest.json').write_text(
        json.dumps(stored, sort_keys=True, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description='Selective generation from a validated snapshot')
    parser.add_argument('--graph', required=True, type=Path)
    parser.add_argument('--snapshot', required=True, type=Path)
    parser.add_argument('--output', default=Path('.cidd/generated-runs'), type=Path)
    parser.add_argument('--model', default=None)
    args = parser.parse_args()
    try:
        result = generate_from_snapshot(args.graph, args.snapshot, args.output,
                                        create_provider(model=args.model))
    except (SnapshotError, GenerationError, ValueError, OSError) as exc:
        parser.exit(1, f'Snapshot selective error: {exc}\n')
    for item in result['results']:
        print(item['status'], item['id'], item['decision'], item.get('error', ''))
    print('Run:', result['run_dir'], 'tokens:', result['input_tokens'] + result['output_tokens'])
    if any(item['status'] == 'FAILED' for item in result['results']):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
