"""Deterministic, conservative Windows Flutter bootstrap for CIDD 0.1."""
from __future__ import annotations

import json
import re
from pathlib import Path

from cidd.engine.sanitizer import _path


class BootstrapError(ValueError):
    pass


def _class_name(cid: str, layer: str) -> str:
    prefix = layer + '.'
    if not cid.startswith(prefix):
        raise BootstrapError(f'Expected {layer} contract, got: {cid}')
    name = cid[len(prefix):]
    if not re.fullmatch(r'[A-Z][A-Za-z0-9_]*', name):
        raise BootstrapError(f'Invalid Dart class name: {cid}')
    return name


def _variable(name: str) -> str:
    return name[0].lower() + name[1:]


def bootstrap_flutter(graph: dict, output: Path, package: str) -> dict:
    """Create Flutter main.dart from a sealed graph; no model calls, no code inspection.

    MVP conventions (validated, not guessed): one presentation screen, one sqlite3
    implementation, and use cases with positional repository constructors; screen
    uses named lowerCamelCase use-case arguments. Unsupported graphs fail closed.
    """
    entries = {c['id']: c for c in graph['contracts']}
    screens = [c for c in graph['contracts'] if c['id'].startswith('presentation.')]
    databases = [c for c in graph['contracts'] if c['id'].startswith('infrastructure.')]
    if len(screens) != 1 or len(databases) != 1:
        raise BootstrapError('MVP requires exactly one presentation and one infrastructure contract')
    screen, adapter = screens[0], databases[0]
    try:
        spec = json.loads(adapter['specification'])
    except (ValueError, TypeError, KeyError) as exc:
        raise BootstrapError('Invalid infrastructure specification') from exc
    if spec.get('provider') != 'sqlite3':
        raise BootstrapError('MVP supports only native sqlite3 persistence')
    screen_deps = [d['id'] for d in screen.get('dependencies', [])]
    usecases = [cid for cid in screen_deps if cid.startswith('application.')]
    if not usecases:
        raise BootstrapError('Presentation contract does not declare application dependencies')
    if len(usecases) != len(set(usecases)) or len(usecases) != len(screen_deps):
        raise BootstrapError('MVP screen must depend only on distinct application use cases')
    for cid in usecases:
        if cid not in entries:
            raise BootstrapError(f'Missing application contract: {cid}')
        deps = {d['id'] for d in entries[cid].get('dependencies', [])}
        repository_ids = [dep for dep in deps if dep.startswith('domain.') and dep.endswith('Repository')]
        if len(repository_ids) != 1:
            raise BootstrapError(f'Expected one repository dependency for {cid}')
        if repository_ids[0] not in {d['id'] for d in adapter.get('dependencies', [])}:
            raise BootstrapError(f'Infrastructure adapter does not declare {repository_ids[0]}')
    screen_name = _class_name(screen['id'], 'presentation')
    adapter_name = _class_name(adapter['id'], 'infrastructure')
    usecase_names = [_class_name(cid, 'application') for cid in usecases]
    imports = sorted([_path(cid, package) for cid in [screen['id'], adapter['id'], *usecases]])
    lines = ["import 'package:flutter/material.dart';", "import 'package:sqlite3/sqlite3.dart';"]
    lines += [f"import '{uri}';" for uri in imports]
    lines += ['', 'void main() {', '  WidgetsFlutterBinding.ensureInitialized();',
              "  final database = sqlite3.open('app.db');",
              f'  final repository = {adapter_name}(database);', '',
              '  runApp(MaterialApp(', '    debugShowCheckedModeBanner: false,',
              f"    title: '{package}',", f'    home: {screen_name}(']
    for name in usecase_names:
        lines.append(f'      {_variable(name)}: {name}(repository),')
    lines += ['    ),', '  ));', '}', '']
    main = output / 'lib' / 'main.dart'
    if not main.is_file():
        raise BootstrapError('Missing Flutter template lib/main.dart')
    original = main.read_text(encoding='utf-8')
    if 'class MyApp' not in original or 'class MyHomePage' not in original:
        raise BootstrapError('Template main.dart is not the supported default Flutter counter template')
    # Never silently delete arbitrary project tests.
    removed = []
    for rel in ('test/widget_test.dart', 'flutter/test/widget_test.dart'):
        test_file = output / rel
        if test_file.is_file():
            content = test_file.read_text(encoding='utf-8')
            if 'MyApp(' in content and 'package:flutter_test/flutter_test.dart' in content:
                test_file.unlink()
                removed.append(rel)
            elif 'MyApp(' in content:
                raise BootstrapError(f'Unsupported template test referring to MyApp: {rel}')
    main.write_text('\n'.join(lines), encoding='utf-8')
    return {'status': 'PASS', 'main': 'lib/main.dart', 'template_tests_removed': removed,
            'entrypoint': screen['id'], 'repository_adapter': adapter['id'],
            'use_cases': usecases, 'mode': 'windows-native-sqlite3-mvp'}
