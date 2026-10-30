"""Offline, conservative CIDD Dart assembly and import resolution.

Usage: python -m cidd.engine.assembly --graph .cidd/contract-graph.json \
  --run .cidd/generated-runs/20261029_152541 --project .
"""
from __future__ import annotations
import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path

from cidd.engine.sanitizer import sanitize_dart, SanitizationError, _path
from cidd.engine.bootstrap import bootstrap_flutter, BootstrapError

_IDENT = re.compile(r'\b[A-Za-z_][A-Za-z_0-9]*\b')
_IMPORT = re.compile(r"(?m)^\s*import\s+['\"]([^'\"]+)['\"]\s*;[^\n]*\n?")
_CLASS = re.compile(r'\b(?:class|enum|mixin|extension\s+type)\s+([A-Za-z_]\w*)')

class AssemblyError(ValueError):
    pass


def _package(project: Path) -> str:
    pubspec = project / 'pubspec.yaml'
    if not pubspec.is_file():
        raise AssemblyError(f'Missing project pubspec.yaml: {pubspec}')
    match = re.search(r'(?m)^name:\s*([a-z][a-z0-9_]*)\s*(?:#.*)?$', pubspec.read_text(encoding='utf-8'))
    if not match:
        raise AssemblyError('Cannot determine Dart package name from pubspec.yaml')
    return match.group(1)


def _read_graph(path: Path) -> dict:
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data.get('contracts'), list) or not data.get('fingerprint'):
        raise AssemblyError('Invalid sealed graph')
    ids = [c['id'] for c in data['contracts']]
    if len(ids) != len(set(ids)):
        raise AssemblyError('Duplicate contract ID')
    return data


def _code_with_imports(source: str, *, current: str, graph: dict, package: str) -> tuple[str, list[str]]:
    entries = {c['id']: c for c in graph['contracts']}
    entry = entries[current]
    direct = {d['id'] for d in entry['dependencies']}
    symbols = {cid.split('.', 1)[1]: cid for cid in entries}
    if len(symbols) != len(entries):
        raise AssemblyError('Ambiguous class name across contracts')
    # Normalize existing imports with the current sanitizer: never accept guessed paths.
    normalized = sanitize_dart(source, contract_id=current,
        dependencies=tuple(sorted(direct)), all_contract_ids=tuple(sorted(entries)),
        package_name=package).source
    existing = set(_IMPORT.findall(normalized))
    body = _IMPORT.sub('', normalized)
    # Public API transitive types may be imported when explicitly named by an authorized
    # direct dependency's sealed interface (e.g. Todo in List<Todo>).
    api_types = set()
    for dep in entry['dependencies']:
        api_types.update(_IDENT.findall(dep['interface']))
    allowed = direct | {cid for symbol, cid in symbols.items()
                        if symbol in api_types and cid != current}
    # Keep symbol resolution conservative: ignore comments and string literals when
    # deciding whether a class is referenced. Dart analyzer is authoritative later.
    scan = re.sub(r'//[^\n]*|/\*[\s\S]*?\*/|\"(?:\\.|[^\"\\])*\"|\'(?:\\.|[^\'\\])*\'', ' ', body)
    # Resolve *only* qualified references to graph-authorized symbols.
    # The masking preserves offsets, so comments and strings are never modified.
    masked = re.sub(r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'',
                    lambda m: ' ' * len(m.group()), body)
    aliases = set(re.findall(r"(?m)^\s*import\s+['\"][^'\"]+['\"]\s+as\s+(\w+)\s*;", normalized))
    fixes = []
    for match in re.finditer(r'\b(domain|application|infrastructure|presentation)\.([A-Za-z_]\w*)\b', masked):
        layer, symbol = match.groups()
        target = f'{layer}.{symbol}'
        if layer in aliases:
            continue
        if target in entries and target != current:
            if target not in allowed:
                raise AssemblyError(f'Undeclared qualified dependency: {target}')
            fixes.append((match.start(), match.end(), symbol))
    for start, end, symbol in reversed(fixes):
        body = body[:start] + symbol + body[end:]
    scan = re.sub(r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', ' ', body)
    used = set(_IDENT.findall(scan))
    required = {cid for name, cid in symbols.items() if name in used and cid != current}
    forbidden = required - allowed
    if forbidden:
        raise AssemblyError('Undeclared referenced contracts: ' + ', '.join(sorted(forbidden)))
    paths = {_path(cid, package) for cid in required}
    for uri in existing:
        if uri.startswith(f'package:{package}/') and uri not in paths:
            # Existing internal imports must be backed by an authorized dependency.
            raise AssemblyError(f'Unexpected internal import: {uri}')
    imports = sorted(existing | paths)
    # An import URI can exist without a known external package; dart analyze will catch it.
    combined = ''.join(f"import '{u}';\n" for u in imports)
    return (combined + '\n' if combined else '') + body.lstrip('\n'), sorted(paths - existing)


def _prepare_dependencies(graph: dict, output: Path) -> list[str]:
    """Pin supported infrastructure packages in the *assembled copy only*."""
    required = set()
    for contract in graph['contracts']:
        if not contract['id'].startswith('infrastructure.'):
            continue
        try:
            spec = json.loads(contract['specification'])
        except (ValueError, TypeError) as exc:
            raise AssemblyError(f"Invalid infrastructure specification: {contract['id']}") from exc
        if spec.get('provider') == 'sqlite3':
            required.add('sqlite3')
    path = output / 'pubspec.yaml'
    content = path.read_text(encoding='utf-8')
    added = []
    if 'sqlite3' in required and not re.search(r'(?m)^\s*sqlite3\s*:', content):
        line = re.search(r'(?m)^dependencies:\s*(?:#.*)?$', content)
        if not line:
            raise AssemblyError('Cannot add sqlite3: missing dependencies section in pubspec.yaml')
        content = content[:line.end()] + '\n  sqlite3: 3.8.0' + content[line.end():]
        added.append('sqlite3: 3.8.0')
    if added:
        path.write_text(content, encoding='utf-8')
    return added


def _run_command(command: list[str], cwd: Path, timeout: int = 180) -> dict:
    try:
        result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return {'status': 'PASS' if result.returncode == 0 else 'FAIL',
                'command': command, 'exit_code': result.returncode,
                'stdout': result.stdout[-40000:], 'stderr': result.stderr[-40000:]}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {'status': 'FAIL', 'command': command, 'diagnostic': str(exc)}


def assemble(graph_path: Path, run_dir: Path, project: Path, output: Path, *, analyze: bool=True) -> dict:
    graph = _read_graph(graph_path)
    package = _package(project)
    if output.exists():
        raise AssemblyError(f'Output already exists: {output}')
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(project, output, ignore=shutil.ignore_patterns('.cidd', '.dart_tool', 'build', '.git', '.idea'))
    items = []
    for contract in graph['contracts']:
        cid = contract['id']
        layer, name = cid.split('.', 1)
        original = run_dir / layer / (name + '.dart')
        if not original.is_file():
            # Fenced failed output is eligible for offline sanitization and recovery.
            original = run_dir / 'failed' / layer / (name + '.raw.txt')
        if not original.is_file():
            items.append({'id':cid, 'status':'MISSING_SOURCE'})
            continue
        try:
            fixed, added = _code_with_imports(original.read_text(encoding='utf-8'),
                current=cid, graph=graph, package=package)
            destination = output / 'lib' / layer / (_path(cid,package).rsplit('/',1)[1])
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(fixed, encoding='utf-8')
            items.append({'id':cid,'status':'ASSEMBLED','path':str(destination.relative_to(output)),
                          'imports_added':added,'recovered_from_failed':'.raw.txt' in original.name})
        except (SanitizationError, AssemblyError) as exc:
            items.append({'id':cid,'status':'FAILED','diagnostic':str(exc)})
    report = {'schema':'cidd.assembly-report/0.1','graph_fingerprint':graph['fingerprint'],
              'package':package,'contracts':items, 'dependencies_added':[],
              'bootstrap':{'status':'NOT_RUN'}, 'pub_get':{'status':'NOT_RUN'}, 'analyzer':{'status':'NOT_RUN'}}
    if all(i['status']=='ASSEMBLED' for i in items):
        try:
            report['bootstrap'] = bootstrap_flutter(graph, output, package)
        except BootstrapError as exc:
            report['bootstrap'] = {'status': 'FAIL', 'diagnostic': str(exc)}
    if analyze and report['bootstrap']['status']=='PASS':
        try:
            report['dependencies_added'] = _prepare_dependencies(graph, output)
        except AssemblyError as exc:
            report['pub_get'] = {'status':'BLOCKED', 'diagnostic':str(exc)}
            report['analyzer'] = {'status':'BLOCKED', 'diagnostic':'Dependency preparation failed'}
        else:
            flutter = shutil.which('flutter')
            dart = shutil.which('dart')
            if flutter:
                report['pub_get'] = _run_command([flutter, 'pub', 'get'], output)
                if report['pub_get']['status'] == 'PASS':
                    report['analyzer'] = _run_command([flutter, 'analyze', '--no-pub', '--no-fatal-infos'], output)
                else:
                    report['analyzer']={'status':'BLOCKED','diagnostic':'flutter pub get failed'}
            elif dart:
                report['pub_get'] = _run_command([dart, 'pub', 'get'], output)
                if report['pub_get']['status'] == 'PASS':
                    report['analyzer'] = _run_command([dart, 'analyze'], output)
                else:
                    report['analyzer']={'status':'BLOCKED','diagnostic':'dart pub get failed'}
            else:
                report['pub_get'] = {'status':'UNAVAILABLE'}
                report['analyzer']={'status':'UNAVAILABLE','diagnostic':'Neither flutter nor dart executable found'}
    elif analyze:
        report['analyzer']={'status':'BLOCKED','diagnostic':'One or more contracts not assembled or bootstrap failed'}
    (output/'cidd-assembly-report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    return report


def main():
    parser=argparse.ArgumentParser(description='Offline CIDD Dart assembly; never invokes LLM')
    parser.add_argument('--graph',type=Path,required=True)
    parser.add_argument('--run',type=Path,required=True)
    parser.add_argument('--project',type=Path,required=True)
    parser.add_argument('--output',type=Path,default=None)
    parser.add_argument('--no-analyze',action='store_true')
    args=parser.parse_args()
    output=args.output or (args.project/'.cidd'/'assembled' / args.run.name)
    result=assemble(args.graph,args.run,args.project,output,analyze=not args.no_analyze)
    print('Assembly:',output)
    for item in result['contracts']:
        print(item['status'],item['id'],item.get('diagnostic',''))
    print('Bootstrap:',result['bootstrap']['status'])
    print('Analyzer:',result['analyzer']['status'])
    print('Report:',output/'cidd-assembly-report.json')
    if result['bootstrap']['status'] != 'PASS' or result['analyzer']['status'] in ('FAIL', 'BLOCKED') or any(i['status']!='ASSEMBLED' for i in result['contracts']):
        raise SystemExit(1)

if __name__=='__main__':
    main()
