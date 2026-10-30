"""One bounded, isolated feedback regeneration with strict provenance.

No source patching: only a full replacement of contracts with analyzer errors.
"""
from __future__ import annotations
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
import time

from cidd.engine.generation import load_verified_graph, GenerationError
from cidd.engine.selective import verified_snapshot, signature, _source_path
from cidd.engine.feedback import route_feedback
from cidd.engine.sanitizer import sanitize_dart
from cidd.workers.isolated import IsolatedWorker
from cidd.providers.factory import create_provider
from cidd.engine.assembly import assemble


def _json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


class FeedbackProvider:
    """Append diagnostic to the original user message, leaving the contract sealed."""
    def __init__(self, upstream, feedback):
        self.upstream = upstream
        self.feedback = feedback

    def generate(self, system_prompt, user_prompt):
        return self.upstream.generate(system_prompt, user_prompt + '\n\nVALIDATION FEEDBACK (FOR THIS CONTRACT ONLY):\n' + self.feedback +
            '\nRegenerate the entire contract source. Do not patch previous code.')


def retry_once(graph_path: Path, run_path: Path, report_path: Path, output_root: Path,
               project: Path, provider, *, run_id: str | None = None, analyze: bool = True):
    contracts = load_verified_graph(graph_path)
    graph = _json(graph_path)
    prior_graph = verified_snapshot(run_path)
    if prior_graph['fingerprint'] != graph['fingerprint']:
        raise GenerationError('Feedback retry requires identical sealed graph to source run')
    previous_manifest = _json(run_path / 'manifest.json')
    report = _json(report_path)
    feedback = route_feedback(graph, report)
    affected = {x['id']: x['feedback'] for x in feedback['affected_contracts']}
    if not affected:
        raise GenerationError('No actionable analyzer errors in report')
    prev = {x['id']: x for x in previous_manifest['results']}
    package_match = re.search(r'(?m)^name:\s*([a-z][a-z0-9_]*)\s*(?:#.*)?$', (project / 'pubspec.yaml').read_text(encoding='utf-8'))
    if not package_match:
        raise GenerationError('Project pubspec.yaml with valid package name required')
    package = package_match.group(1)
    run_id = run_id or datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    if not re.fullmatch(r'[A-Za-z0-9_-]+', run_id):
        raise GenerationError('Unsafe run ID')
    target_run = output_root / run_id
    target_run.mkdir(parents=True, exist_ok=False)
    shutil.copy2(graph_path, target_run / 'sealed-graph.json')
    results = []
    for contract in contracts:
        cid = contract.contract_id
        rel = _source_path(cid, contract.language)
        dest = target_run / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        item = dict(id=cid, status='FAILED', decision='FEEDBACK_RETRY' if cid in affected else 'UNCHANGED',
                    contract_hash=signature(next(c for c in graph['contracts'] if c['id'] == cid)),
                    input_tokens=0, output_tokens=0, elapsed_seconds=0.0)
        start = time.perf_counter()
        response = None
        try:
            if cid not in affected:
                old_entry = prev.get(cid, {})
                if old_entry.get('status') not in ('GENERATED', 'REUSED') or not old_entry.get('path'):
                    raise GenerationError(f'Cannot reuse unsuccessful/missing prior contract: {cid}')
                old_rel = Path(old_entry['path'])
                if old_rel.is_absolute() or '..' in old_rel.parts or old_rel != rel:
                    raise GenerationError(f'Unsafe or mismatched source path: {cid}')
                src = run_path / old_rel
                data = src.read_bytes()
                if old_entry.get('source_sha256') and hashlib.sha256(data).hexdigest() != old_entry['source_sha256']:
                    raise GenerationError(f'Modified source: {cid}')
                dest.write_bytes(data)
                item.update(status='REUSED', origin_run=run_path.name, origin_path=old_rel.as_posix())
            else:
                response = IsolatedWorker(FeedbackProvider(provider, affected[cid])).generate(contract).response
                item['input_tokens'] = response.input_tokens
                item['output_tokens'] = response.output_tokens
                if contract.language.lower() == 'dart':
                    source = sanitize_dart(response.content, contract_id=cid,
                        dependencies=tuple(d.contract_id for d in contract.dependencies),
                        all_contract_ids=tuple(c.contract_id for c in contracts), package_name=package).source
                else:
                    source = response.content.strip() + '\n'
                if not source.strip() or '```' in source:
                    raise GenerationError('Empty or ambiguous LLM output')
                dest.write_text(source, encoding='utf-8')
                item['status'] = 'GENERATED'
            item['path'] = rel.as_posix()
            item['source_sha256'] = hashlib.sha256(dest.read_bytes()).hexdigest()
        except Exception as exc:
            item['error'] = f'{type(exc).__name__}: {exc}'
            if response is not None:
                failure = target_run / 'failed' / rel.parent / (rel.stem + '.raw.txt')
                failure.parent.mkdir(parents=True, exist_ok=True)
                failure.write_text(response.content, encoding='utf-8')
                item['raw_response_path'] = failure.relative_to(target_run).as_posix()
        finally:
            item['elapsed_seconds'] = round(time.perf_counter() - start, 4)
            results.append(item)
    manifest = dict(schema='cidd.generation-run/0.1', graph_fingerprint=graph['fingerprint'],
        results=results, input_tokens=sum(x['input_tokens'] or 0 for x in results),
        output_tokens=sum(x['output_tokens'] or 0 for x in results),
        token_counts_complete=all(x['status'] != 'FAILED' for x in results),
        feedback_source=str(report_path), retry_attempt=1)
    (target_run / 'manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    assembly_result = None
    if all(x['status'] != 'FAILED' for x in results):
        assembly_result = assemble(graph_path, target_run, project, project / '.cidd' / 'assembled' / run_id, analyze=analyze)
    return {'run_dir': str(target_run), 'manifest': manifest, 'assembly': assembly_result}


def main():
    p = argparse.ArgumentParser(description='One isolated, bounded analyzer-feedback retry')
    p.add_argument('--graph', type=Path, required=True)
    p.add_argument('--run', type=Path, required=True, help='Previous run, with sealed-graph.json')
    p.add_argument('--report', type=Path, required=True)
    p.add_argument('--project', type=Path, required=True)
    p.add_argument('--output', type=Path, default=Path('.cidd/generated-runs'))
    p.add_argument('--model', required=True)
    args = p.parse_args()
    result = retry_once(args.graph, args.run, args.report, args.output, args.project, create_provider(model=args.model))
    for e in result['manifest']['results']:
        print(e['status'], e['id'], e['decision'], e.get('error',''))
    print('New run:', result['run_dir'])
    print('Tokens:', result['manifest']['input_tokens'] + result['manifest']['output_tokens'])
    if result['assembly']:
        print('Analyzer:', result['assembly']['analyzer']['status'])
    if any(e['status']=='FAILED' for e in result['manifest']['results']) or not result['assembly'] or result['assembly']['analyzer']['status']!='PASS':
        raise SystemExit(1)

if __name__ == '__main__':
    main()
