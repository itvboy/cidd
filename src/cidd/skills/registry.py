"""Resolve implementation instructions before a contract is sealed."""
from pathlib import Path
import yaml

_SKILL_BY_KIND = {
    ('domain', 'entity'): 'entity',
    ('domain', 'repository'): 'repository',
    ('application', 'use_case'): 'use_case',
    ('infrastructure', 'persistence'): 'persistence',
    ('presentation', 'screen'): 'screen',
}


def resolve_skill(language: str, contract_id: str, entry: dict) -> str:
    """Return text to embed in the sealed contract; no LLM and no repo inspection."""
    if language.lower() != 'dart':
        return entry.get('skill', '')
    layer, _, name = contract_id.partition('.')
    if layer == 'domain':
        kind = 'entity' if isinstance(entry.get('fields'), list) else 'repository'
    else:
        kind = {'application': 'use_case', 'infrastructure': 'persistence',
                'presentation': 'screen'}.get(layer)
    if not kind:
        return entry.get('skill', '')
    explicit = entry.get('skill', '')
    if explicit:
        return explicit  # preserve explicit instruction text
    path = Path(__file__).parent / 'dart' / f'{kind}.yaml'
    if not path.is_file():
        raise ValueError(f'Missing implementation skill: {path}')
    data = yaml.safe_load(path.read_text(encoding='utf-8'))
    rules = data.get('rules') if isinstance(data, dict) else None
    if not isinstance(rules, list) or not rules or not all(isinstance(r, str) and r.strip() for r in rules):
        raise ValueError(f'Invalid implementation skill: {path}')
    return '\n'.join(f'- {rule}' for rule in rules)
