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
_IMPORT = re.compile(
    r"^(?P<indent>[ \t]*)import[ \t]+"
    r"['\"](?P<uri>[^'\"]+)['\"]"
    r"(?P<alias>[ \t]+as[ \t]+[A-Za-z_]\w*)?"
    r"[ \t]*;(?P<tail>[ \t]*(?://[^\r\n]*)?)$",
    re.MULTILINE,
)
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

    validate_contract_ownership(
        source=source,
        contract_id=contract_id,
        dependencies=dependencies,
    )

    paths = {cid: _path(cid, package_name) for cid in deps}

    # Only identify imports belonging to declared direct dependencies.
    replacements = 0
    retained: list[str] = []
    imports_seen: set[tuple[str, str]] = set()
    for match in list(_IMPORT.finditer(source)):
        uri = match.group('uri')
        alias = match.group('alias') or ''

        # Remove unused self-imports deterministically.
        layer, name = contract_id.split('.', 1)

        self_imports = {
            _path(contract_id, package_name),
            f'package:{layer}.{name}',
            f'package:{layer}.{name}.dart',
        }

        if uri in self_imports:
            alias_name = alias.strip().removeprefix('as ').strip()

            # Never remove a self-import if its alias is referenced.
            if alias_name and re.search(
                rf'\b{re.escape(alias_name)}\s*\.',
                _IMPORT.sub('', source),
            ):
                raise SanitizationError(
                    f'Self-import alias is referenced: {alias_name}'
                )

            replacements += 1
            continue

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
                    f'package:{layer}.{name}',
                    f'package:{layer}.{name}.dart',
                }
                if uri in guessed:
                    candidates.append(real_uri)
            if len(candidates) == 1:
                resolved = candidates[0]
        if resolved is None:
            if (
                uri.startswith(_EXTERNAL_PREFIXES)
                or any(
                    uri.startswith(prefix)
                    if prefix.endswith("/")
                    else uri == prefix
                    for prefix in allowed_external
                )
            ):
                resolved = uri
            else:
                raise SanitizationError(f'Unknown or undeclared import: {uri}')
        if resolved != uri:
            replacements += 1
        key = (resolved, alias.strip())
        if key not in imports_seen:
            retained.append(f"import '{resolved}'{alias};")
            imports_seen.add(key)
    # Remove existing import statements, then prepend canonical imports.
    body = _IMPORT.sub('', source).lstrip('\n')
    # Do not invent imports for dependencies not used: the assembly stage will
    # determine symbol usage; adding all direct imports causes unused-import lints.
    header = '\n'.join(retained)
    normalized = (header + '\n\n' if header else '') + body.rstrip() + '\n'
    return SanitizationResult(normalized, bool(fenced), replacements, 0)

def validate_contract_ownership(
    source: str,
    contract_id: str,
    dependencies: tuple[str, ...],
) -> None:
    """Reject declarations that redefine dependency contracts."""

    dependency_names = {
        dependency.split(".", 1)[1]
        for dependency in dependencies
    }

    declared_names = set(
        re.findall(
            r"\b(?:abstract\s+interface\s+class|"
            r"abstract\s+class|class)\s+"
            r"([A-Za-z_]\w*)",
            source,
        )
    )

    violations = declared_names & dependency_names

    if violations:
        raise SanitizationError(
            "Worker redefined dependency contracts: "
            + ", ".join(sorted(violations))
        )