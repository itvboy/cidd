"""Conservative, deterministic Dart source normalization for CIDD staging."""
from __future__ import annotations
import re
from dataclasses import dataclass

class SanitizationError(ValueError):
    pass

@dataclass(frozen=True)
class SanitizationResult:
    source: str
    markdown_removed: bool
    imports_rewritten: int
    imports_added: int

_FENCE = re.compile(r'\A\s*```(?:dart)?[ \t]*\r?\n(?P<code>.*?)\r?\n```[ \t]*\s*\Z', re.DOTALL | re.IGNORECASE)
_IMPORT = re.compile(r"^(?P<indent>\s*)import\s+['\"](?P<uri>[^'\"]+)['\"]\s*;(?P<tail>\s*(?://.*)?)$", re.MULTILINE)
_EXTERNAL_PREFIXES = ('dart:', 'package:flutter/', 'package:sqlite3/')
_LAYERS = ('domain', 'application', 'infrastructure', 'presentation')

def _snake(name: str) -> str:
    return re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()

def _path(contract_id: str, package_name: str) -> str:
    layer, name = contract_id.split('.', 1)
    return f'package:{package_name}/{layer}/{_snake(name)}.dart'

def sanitize_dart(raw: str, *, contract_id: str, dependencies: tuple[str, ...],
                  all_contract_ids: tuple[str, ...], package_name: str,
                  allowed_external: tuple[str, ...] = ()) -> SanitizationResult:
    if not re.fullmatch(r'[a-z][a-z0-9_]*', package_name):
        raise SanitizationError('Invalid Dart package name')
    fenced = _FENCE.fullmatch(raw)
    if fenced:
        source = fenced.group('code').strip() + '\n'
    else:
        if '```' in raw:
            raise SanitizationError('Ambiguous Markdown or multiple code fences')
        source = raw.strip() + '\n'
    if not source.strip():
        raise SanitizationError('Empty source')
    contract_ids = set(all_contract_ids)
    if contract_id not in contract_ids:
        raise SanitizationError('Current contract missing from graph')
    deps = set(dependencies)
    if not deps.issubset(contract_ids):
        raise SanitizationError('Dependency missing from graph')
    paths = {cid: _path(cid, package_name) for cid in deps}
    # Only identify imports belonging to declared direct dependencies.
    replacements = 0
    retained: list[str] = []
    imports_seen: set[str] = set()
    for match in list(_IMPORT.finditer(source)):
        uri = match.group('uri')
        resolved = None
        if uri in paths.values():
            resolved = uri
        else:
            # Recognize package:layer/Class.dart, layer.Class.dart, and layer/Class.dart.
            candidates = []
            for cid, real_uri in paths.items():
                layer, name = cid.split('.', 1)
                guessed = {
                    f'{layer}.{name}',
                    f'{layer}.{name}.dart',
                    f'package:{layer}/{name}.dart',
                    f'package:{layer}/{_snake(name)}.dart',
                    f'{layer}/{name}.dart',
                    f'{layer}/{_snake(name)}.dart',
                }
                if uri in guessed:
                    candidates.append(real_uri)
            if len(candidates) == 1:
                resolved = candidates[0]
        if resolved is None:
            if uri.startswith(_EXTERNAL_PREFIXES) or uri in allowed_external:
                resolved = uri
            else:
                raise SanitizationError(f'Unknown or undeclared import: {uri}')
        if resolved != uri:
            replacements += 1
        if resolved not in imports_seen:
            retained.append(f"import '{resolved}';")
            imports_seen.add(resolved)
    # Remove existing import statements, then prepend canonical imports.
    body = _IMPORT.sub('', source).lstrip('\n')
    # Do not invent imports for dependencies not used: the assembly stage will
    # determine symbol usage; adding all direct imports causes unused-import lints.
    header = '\n'.join(retained)
    normalized = (header + '\n\n' if header else '') + body.rstrip() + '\n'
    return SanitizationResult(normalized, bool(fenced), replacements, 0)
