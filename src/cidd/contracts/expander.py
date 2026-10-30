"""LLM-assisted repository contract expansion, prior to deterministic graph sealing.

The genome is never mutated; a proposed interface is reviewed structurally first.
"""
from __future__ import annotations

from copy import deepcopy
import json
import re

from cidd.genome.parser import GenomeError
from cidd.providers.base import LLMProvider, LLMResponse

DART_REPOSITORY_RULES = """Derive a Dart repository interface from the entity and use cases.
Only include persistence operations required by those use cases.
Do not copy use-case names into repository methods.
No implementation, SQL, business workflows, extra classes, imports or markdown.
Use explicit Dart parameter and return types. Prefer add/update over generic upsert.
Return one valid JSON object with one key: interface.
The interface must be a Dart abstract class named {repository_name}.
"""


def _contract_name(entry: dict) -> str:
    return entry.get('id') or entry.get('name') or ''


def _extract_interface(raw: str, expected_name: str) -> str:
    try:
        value = json.loads(raw.strip())
    except json.JSONDecodeError as exc:
        raise GenomeError('Repository expansion: LLM must return a JSON object') from exc
    code = value.get('interface') if isinstance(value, dict) else None
    if not isinstance(code, str) or not code.strip():
        raise GenomeError('Repository expansion: missing interface string')
    code = code.strip()
    if not re.search(r'\babstract\s+class\s+' + re.escape(expected_name) + r'\b', code):
        raise GenomeError(f'Repository expansion: expected abstract class {expected_name}')
    if code.count('{') != 1 or code.count('}') != 1 or not code.endswith('}'):
        raise GenomeError('Repository expansion: expected one interface with balanced braces')
    if re.search(r'```|\bimport\s|\bclass\s+(?!' + re.escape(expected_name) + r'\b)', code):
        raise GenomeError('Repository expansion: imports, markdown and other classes disallowed')
    body = code[code.index('{') + 1:code.rindex('}')]
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    if not lines or any(not line.endswith(';') or '(' not in line or ')' not in line for line in lines):
        raise GenomeError('Repository expansion: expected abstract method signatures only')
    return code


def expand_repository_contracts(genome: dict, provider: LLMProvider) -> tuple[dict, list[LLMResponse]]:
    """Return a new genome plus LLM usage. MVP supports one entity per project.

    No files are written; failure prevents publication of a new sealed graph.
    """
    expanded = deepcopy(genome)
    entities = expanded['domain']['entities']
    use_cases = expanded['application']['use_cases']
    if not entities or not use_cases:
        return expanded, []
    if len(entities) != 1:
        raise GenomeError('MVP repository expansion supports exactly one entity per application')
    if expanded['project'].get('language', '').lower() != 'dart':
        raise GenomeError('MVP repository expansion currently supports Dart only')
    entity = entities[0]
    entity_name = _contract_name(entity)
    if not entity_name:
        raise GenomeError('Entity requires name')
    repo_name = entity_name + 'Repository'
    repo_id = 'domain.' + repo_name
    if any(_contract_name(item) == repo_name for item in entities):
        raise GenomeError(f'{repo_id}: already declared; repository must be derived')
    prompt = json.dumps({'entity': entity, 'use_cases': use_cases}, ensure_ascii=False, sort_keys=True)
    response = provider.generate(DART_REPOSITORY_RULES.format(repository_name=repo_name), prompt)
    interface = _extract_interface(response.content, repo_name)
    entities.append({'name': repo_name, 'interface': interface,
                     'description': f'Derived repository interface for {entity_name}',
                     'depends_on': ['domain.' + entity_name]})
    # The cases explicitly depend on entity and newly derived repository.
    for use_case in use_cases:
        deps = use_case.setdefault('depends_on', [])
        for dep in ('domain.' + entity_name, repo_id):
            if dep not in deps:
                deps.append(dep)
    # Existing presentation and infrastructure references are not guessed by an LLM.
    return expanded, [response]
