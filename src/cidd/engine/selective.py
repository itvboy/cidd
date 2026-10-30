"""Provenance-checked CIDD selective generation (experimental CLI).

python -m cidd.engine.selective --graph .cidd/contract-graph.json \
    --reuse-run .cidd/generated-runs/BASELINE --output .cidd/generated-runs
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import shutil
import time
from datetime import datetime
from pathlib import Path

from cidd.engine.generation import load_verified_graph, GenerationError
from cidd.workers.isolated import IsolatedWorker
from cidd.providers.factory import create_provider

EXT = {'dart': '.dart', 'go': '.go', 'python': '.py'}
SAFE_ID = re.compile(r'^[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+$')


def signature(item: dict) -> str:
    """Hash the full worker-visible contract input, not just its name."""
    normalized = {key: item[key] for key in ('id', 'language', 'specification', 'skill', 'dependencies')}
    payload = json.dumps(normalized, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def verified_snapshot(run: Path) -> dict:
    path = run / 'sealed-graph.json'
    if not path.is_file():
        raise GenerationError(f'Cannot reuse {run}: sealed-graph.json missing. Generate a new baseline first.')
    old = json.loads(path.read_text(encoding='utf-8'))
    load_verified_graph(path)
    manifest_file = run / 'manifest.json'
    if not manifest_file.is_file():
        raise GenerationError(f'Missing previous manifest: {manifest_file}')
    manifest = json.loads(manifest_file.read_text(encoding='utf-8'))
    if manifest.get('graph_fingerprint') != old['fingerprint']:
        raise GenerationError('Previous manifest and sealed graph disagree')
    return old


def plan(current: dict, old: dict, previous_manifest: dict) -> dict[str, str]:
    before = {c['id']: c for c in old['contracts']}
    successful = {e['id']: e for e in previous_manifest.get('results', [])
                  if e.get('status') in ('GENERATED', 'REUSED')}
    decisions = {}
    for new in current['contracts']:
        cid = new['id']
        if cid not in before:
            decisions[cid] = 'NEW'
        elif signature(new) != signature(before[cid]):
            decisions[cid] = 'CHANGED'
        elif cid not in successful or not successful[cid].get('path'):
            decisions[cid] = 'MISSING_SOURCE'
        else:
            decisions[cid] = 'UNCHANGED'
    return decisions


def _source_path(cid: str, language: str) -> Path:
    if not SAFE_ID.fullmatch(cid) or language.lower() not in EXT:
        raise GenerationError(f'Unsafe contract identifier or language: {cid} ({language})')
    layer, name = cid.split('.', 1)
    return Path(layer) / (name + EXT[language.lower()])


def selective_generate(graph_path: Path, previous_run: Path, output_root: Path, provider,
                       *, run_id: str | None = None) -> dict:
    contracts = load_verified_graph(graph_path)
    current = json.loads(graph_path.read_text(encoding='utf-8'))
    old = verified_snapshot(previous_run)
    previous_manifest = json.loads((previous_run / 'manifest.json').read_text(encoding='utf-8'))
    decisions = plan(current, old, previous_manifest)
    previous_entries = {e['id']: e for e in previous_manifest.get('results', [])}
    run_id = run_id or datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    if not re.fullmatch(r'[A-Za-z0-9_-]+', run_id):
        raise GenerationError('Invalid run id')
    run_dir = output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    # Snapshot the exact verified current graph before any model call.
    shutil.copyfile(graph_path, run_dir / 'sealed-graph.json')
    worker = IsolatedWorker(provider)
    results = []
    for contract in contracts:
        cid = contract.contract_id
        target_rel = _source_path(cid, contract.language)
        target = run_dir / target_rel
        target.parent.mkdir(parents=True, exist_ok=True)
        start = time.perf_counter()
        item = {'id': cid, 'status': 'FAILED', 'decision': decisions[cid],
                'contract_hash': signature(next(x for x in current['contracts'] if x['id'] == cid)),
                'input_tokens': 0, 'output_tokens': 0, 'elapsed_seconds': 0.0}
        try:
            if decisions[cid] == 'UNCHANGED':
                old_entry = previous_entries[cid]
                previous_rel = Path(old_entry['path'])
                if previous_rel.is_absolute() or '..' in previous_rel.parts:
                    raise GenerationError(f'Unsafe previous path for {cid}')
                old_path = previous_run / previous_rel
                if not old_path.is_file():
                    raise GenerationError(f'Previous source missing for {cid}: {old_path}')
                # Verify source provenance when a hash is available.
                content = old_path.read_bytes()
                if old_entry.get('source_sha256') and hashlib.sha256(content).hexdigest() != old_entry['source_sha256']:
                    raise GenerationError(f'Previous source modified: {cid}')
                target.write_bytes(content)
                item.update(status='REUSED', origin_run=previous_run.name, origin_path=previous_rel.as_posix())
            else:
                response = worker.generate(contract).response
                item['input_tokens'] = response.input_tokens
                item['output_tokens'] = response.output_tokens
                from cidd.engine.sanitizer import sanitize_dart, SanitizationError
                if contract.language.lower() == 'dart':
                    pubspec = graph_path.parent.parent / 'pubspec.yaml'
                    match = re.search(r'(?m)^name:\s*([a-z][a-z0-9_]*)\s*(?:#.*)?$', pubspec.read_text(encoding='utf-8')) if pubspec.is_file() else None
                    if not match:
                        raise GenerationError('pubspec.yaml with valid package name required for Dart selective generation')
                    source = sanitize_dart(response.content, contract_id=cid,
                        dependencies=tuple(d.contract_id for d in contract.dependencies),
                        all_contract_ids=tuple(c.contract_id for c in contracts),
                        package_name=match.group(1)).source.strip()
                else:
                    source = response.content.strip()
                if not source or '```' in source:
                    raise GenerationError('Invalid source output')
                target.write_text(source + '\n', encoding='utf-8')
                item['status'] = 'GENERATED'
            item['path'] = target_rel.as_posix()
            item['source_sha256'] = hashlib.sha256(target.read_bytes()).hexdigest()
        except Exception as exc:
            item['error'] = f'{type(exc).__name__}: {exc}'
            if 'response' in locals():
                failure = run_dir / 'failed' / target_rel.parent / (target_rel.stem + '.raw.txt')
                failure.parent.mkdir(parents=True, exist_ok=True)
                failure.write_text(response.content, encoding='utf-8')
                item['raw_response_path'] = failure.relative_to(run_dir).as_posix()
        finally:
            if 'response' in locals():
                del response
            item['elapsed_seconds'] = round(time.perf_counter() - start, 4)
            results.append(item)
            manifest = {'schema':'cidd.generation-run/0.1','graph_fingerprint':current['fingerprint'],
                'results':results, 'input_tokens':sum((x.get('input_tokens') or 0) for x in results),
                'output_tokens':sum((x.get('output_tokens') or 0) for x in results),
                'token_counts_complete':all(x.get('status') != 'FAILED' for x in results)}
            (run_dir / 'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return {**manifest, 'run_dir':str(run_dir)}


def main():
    parser = argparse.ArgumentParser(description='Selective CIDD generation with strict sealed-graph provenance')
    parser.add_argument('--graph',type=Path,default=Path('.cidd/contract-graph.json'))
    parser.add_argument('--reuse-run',type=Path,required=True)
    parser.add_argument('--output',type=Path,default=Path('.cidd/generated-runs'))
    parser.add_argument('--model',default=None)
    args = parser.parse_args()
    report = selective_generate(args.graph,args.reuse_run,args.output,create_provider(model=args.model))
    for entry in report['results']:
        print(entry['status'],entry['id'],entry['decision'],entry.get('error',''))
    print('Run:',report['run_dir'],'tokens:',report['input_tokens']+report['output_tokens'])
    if any(e['status']=='FAILED' for e in report['results']):
        raise SystemExit(1)

if __name__ == '__main__':
    main()
