"""E02: incremental Dart repository expansion from a previously sealed graph.

An LLM proposes *only additions*. CIDD merges method declarations and never lets
it rewrite an existing public signature. The original graph remains untouched.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
import re
from pathlib import Path

from cidd.contracts.expander import expand_repository_contracts, _extract_interface
from cidd.contracts.materializer import build_graph, write_graph
from cidd.genome.parser import GenomeError, load_genome
from cidd.genome.validator import validate_genome
from cidd.providers.factory import create_provider
from cidd.providers.base import LLMProviderError

_DELTA_RULES = """You are extending a SEALED Dart repository API.
Existing declarations are immutable and MUST NOT be repeated or rewritten.
Derive only missing persistence methods required by NEW use cases.
Use explicit Dart types; preserve synchronous conventions.
Return ONLY one JSON object: {"add_methods": ["bool deleteById(int id);"]}.
Each entry must be exactly one Dart abstract method declaration ending in ';'.
Return an empty list if no new persistence method is needed.
Do not output classes, imports, comments, markdown, or business workflows.
"""
_METHOD = re.compile(r"^(?P<return>[A-Za-z_][\w<>?, ]*)\s+(?P<name>[A-Za-z_]\w*)\s*\([^;{}]*\)\s*;$")


def _methods(interface: str, repository_name: str) -> list[str]:
    validated = _extract_interface(json.dumps({'interface': interface}), repository_name)
    body = validated.split('{', 1)[1].rsplit('}', 1)[0]
    methods = [line.strip() for line in body.splitlines() if line.strip()]
    seen = set()
    for line in methods:
        match = _METHOD.fullmatch(line)
        if match is None or match.group('name') in seen:
            raise GenomeError(f'Unsupported or duplicate repository method: {line!r}')
        seen.add(match.group('name'))
    return methods


def _old_spec(contract: dict) -> dict:
    try:
        value = json.loads(contract['specification'])
    except (KeyError, TypeError, ValueError) as exc:
        raise GenomeError('Invalid previous sealed contract specification') from exc
    if not isinstance(value, dict):
        raise GenomeError('Invalid previous specification object')
    return value


def incremental_expand(genome: dict, provider, previous_graph: dict):
    """Return expanded genome and LLM usage. Does not change either input."""
    if not isinstance(previous_graph.get('contracts'), list) or not previous_graph.get('fingerprint'):
        raise GenomeError('Invalid previous sealed graph')
    indexed = {c['id']: c for c in previous_graph['contracts']}
    if len(indexed) != len(previous_graph['contracts']):
        raise GenomeError('Duplicate IDs in previous graph')
    validate_genome(genome)
    entities = genome['domain']['entities']
    if len(entities) != 1:
        raise GenomeError('Incremental repository MVP requires one entity')
    entity = entities[0]
    name = entity.get('name') or entity.get('id')
    repo_name = name + 'Repository'
    repo_id = 'domain.' + repo_name
    if repo_id not in indexed:
        return expand_repository_contracts(genome, provider)
    if ('domain.' + name) not in indexed:
        raise GenomeError('Previous entity contract missing')
    old_entity = _old_spec(indexed['domain.' + name])
    if old_entity.get('fields') != entity.get('fields'):
        raise GenomeError('Entity fields changed; incremental repository expansion is not supported')
    prior = _old_spec(indexed[repo_id]); prior_interface = prior.get('interface')
    if not isinstance(prior_interface, str):
        raise GenomeError('Previous repository has no sealed interface')
    old_methods = _methods(prior_interface, repo_name)
    old_names = {_METHOD.fullmatch(s).group('name') for s in old_methods}
    new_cases = []
    for case in genome['application']['use_cases']:
        cid = 'application.' + (case.get('id') or case.get('name'))
        if cid not in indexed:
            new_cases.append(case)
            continue
        old_case = _old_spec(indexed[cid])
        for field in ('input', 'output', 'rules'):
            if old_case.get(field) != case.get(field):
                raise GenomeError(f'{cid}: existing use case changed ({field}); requires a separate evolution policy')
    old_case_ids = {cid for cid in indexed if cid.startswith('application.')}
    current_case_ids = {'application.' + (x.get('id') or x.get('name')) for x in genome['application']['use_cases']}
    if old_case_ids - current_case_ids:
        raise GenomeError('Deleted use cases require a separate evolution policy')
    usage = []
    additions = []
    if new_cases:
        request = {'entity': entity, 'sealed_repository_interface': prior_interface,
                   'new_use_cases': new_cases}
        response = provider.generate(_DELTA_RULES, json.dumps(request, ensure_ascii=False, sort_keys=True))
        usage.append(response)
        try:
            data = json.loads(response.content.strip())
        except (ValueError, AttributeError) as exc:
            raise GenomeError('Incremental expansion requires a JSON object') from exc
        if not isinstance(data, dict) or set(data) != {'add_methods'} or not isinstance(data['add_methods'], list):
            raise GenomeError('Incremental expansion requires exactly {"add_methods": [...]}')
        for raw in data['add_methods']:
            if not isinstance(raw, str):
                raise GenomeError('Incremental expansion methods must be strings')
            method = raw.strip()
            match = _METHOD.fullmatch(method)
            if not match:
                raise GenomeError(f'Invalid incremental method declaration: {method!r}')
            if match.group('name') in old_names:
                raise GenomeError(f'LLM attempted to redefine existing repository method: {match.group("name")}')
            old_names.add(match.group('name'))
            additions.append(method)
    merged = 'abstract class ' + repo_name + ' {\n'
    merged += ''.join('  ' + m + '\n' for m in old_methods + additions) + '}'
    expanded = deepcopy(genome)
    expanded['domain']['entities'].append({
        'name': repo_name, 'interface': merged,
        'description': f'Derived repository interface for {name}',
        'depends_on': ['domain.' + name],
    })
    for case in expanded['application']['use_cases']:
        deps = case.setdefault('depends_on', [])
        for dep in ('domain.' + name, repo_id):
            if dep not in deps:
                deps.append(dep)
    return expanded, usage


def main() -> None:
    parser = argparse.ArgumentParser(description='CIDD E02 incremental repository expansion')
    parser.add_argument('--genome', type=Path, default=Path('genome/genome.yaml'))
    parser.add_argument('--previous-graph', required=True, type=Path)
    parser.add_argument('--output', type=Path, default=Path('.cidd/contract-graph.e02.json'))
    parser.add_argument('--model', default='muse-glimmer')
    args = parser.parse_args()
    try:
        previous = json.loads(args.previous_graph.read_text(encoding='utf-8'))
        genome = load_genome(args.genome)
        expanded, usage = incremental_expand(genome, create_provider(model=args.model), previous)
        graph = build_graph(expanded)
        write_graph(graph, args.output)
    except (GenomeError, LLMProviderError, ValueError, OSError) as exc:
        parser.exit(1, f'[FAIL] {exc}\n')
    for response in usage:
        print(f'[LLM] Delta expansion input={response.input_tokens} output={response.output_tokens}')
    print(f'[PASS] Sealed graph: {len(graph.contracts)} contracts')
    print(f'Fingerprint: {graph.fingerprint}')
    print(f'Written: {args.output}')


if __name__ == '__main__':
    main()
