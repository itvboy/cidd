"""Deterministic, conservative Windows Flutter bootstrap for CIDD 0.1."""
from __future__ import annotations

import json
import re
from pathlib import Path

from cidd.engine.sanitizer import _path
from cidd.contracts.navigation import screen_route
from cidd.engine.integrations import mapbox_configuration

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

def _screen_route(screen_name: str) -> str:
    try:
        return screen_route(screen_name)
    except ValueError as exc:
        raise BootstrapError(str(exc)) from exc

def _bootstrap_flutter_legacy(graph: dict, output: Path, package: str) -> dict:
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
    if (
        len(screen_deps) != len(set(screen_deps))
        or any(
            not cid.startswith(("application.", "domain."))
            for cid in screen_deps
        )
    ):
        raise BootstrapError(
            "MVP screen dependencies must be application or domain contracts"
        )

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


    imports = sorted([
        _path(cid, package)
        for cid in [screen['id'], adapter['id'], *usecases]
    ])

    lines = [
        "import 'package:flutter/material.dart';",
        "import 'package:sqlite3/sqlite3.dart';",
        "import 'package:path/path.dart' as p;",
        "import 'package:path_provider/path_provider.dart';",
    ]

    lines += [f"import '{uri}';" for uri in imports]

    lines += [
        '',
        'Future<void> main() async {',
        '  WidgetsFlutterBinding.ensureInitialized();',
        '',
        '  final directory = await getApplicationSupportDirectory();',
        "  final databasePath = p.join(directory.path, 'app.db');",
        '  final database = sqlite3.open(databasePath);',
        '',
        f'  final repository = {adapter_name}(database);',
        '',
        '  runApp(MaterialApp(',
        '    debugShowCheckedModeBanner: false,',
        f"    title: '{package}',",
        f'    home: {screen_name}(',
    ]


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



def _bootstrap_flutter_multiscreen(
    graph: dict,
    output: Path,
    package: str,
) -> dict:
    entries = {c["id"]: c for c in graph["contracts"]}

    screens = [
        c for c in graph["contracts"]
        if c["id"].startswith("presentation.")
    ]
    adapters = [
        c for c in graph["contracts"]
        if c["id"].startswith("infrastructure.")
    ]

    presentation = graph.get("presentation") or {}
    entry_name = presentation.get("entry_screen")

    if not isinstance(entry_name, str) or not entry_name:
        raise BootstrapError(
            "Multi-screen graph requires entry_screen"
        )

    screen_names = {
        _class_name(c["id"], "presentation"): c
        for c in screens
    }

    if entry_name not in screen_names:
        raise BootstrapError(
            f"Unknown entry screen: {entry_name}"
        )

    if len(adapters) != 1:
        raise BootstrapError(
            "Multi-screen MVP requires one infrastructure adapter"
        )

    adapter = adapters[0]
    adapter_spec = json.loads(adapter["specification"])

    provider = adapter_spec.get("provider")

    if provider not in ("sqlite3", "http"):
        raise BootstrapError(
            f"Unsupported multi-screen provider: {provider}"
        )

    uses_mapbox = any(
        json.loads(screen["specification"]).get("map", {}).get("provider")
        == "mapbox"
        for screen in screens
    )


    adapter_name = _class_name(
        adapter["id"], "infrastructure"
    )

    adapter_dependencies = {
        d["id"] for d in adapter.get("dependencies", [])
    }

    routes = {}
    for screen_name in screen_names:
        route = _screen_route(screen_name)

        if route in routes:
            raise BootstrapError(
                f"Duplicate Flutter route: {route}"
            )

        routes[route] = screen_name

    entry_route = _screen_route(entry_name)

    # Collect only use cases actually required by screens.
    screen_usecases = {}
    all_usecases = set()

    for screen_name, screen in screen_names.items():
        dependencies = [
            d["id"] for d in screen.get("dependencies", [])
        ]

        if len(dependencies) != len(set(dependencies)):
            raise BootstrapError(
                f"{screen_name}: duplicate dependencies"
            )

        if any(
            not dep.startswith(("application.", "domain."))
            for dep in dependencies
        ):
            raise BootstrapError(
                f"{screen_name}: unsupported dependency"
            )

        usecases = [
            dep for dep in dependencies
            if dep.startswith("application.")
        ]

        for cid in usecases:
            if cid not in entries:
                raise BootstrapError(
                    f"Missing application contract: {cid}"
                )

            repository_ids = [
                d["id"]
                for d in entries[cid].get("dependencies", [])
                if d["id"].startswith("domain.")
                and d["id"].endswith("Repository")
            ]

            if (
                len(repository_ids) != 1
                or repository_ids[0] not in adapter_dependencies
            ):
                raise BootstrapError(
                    f"{cid}: unsupported repository dependency"
                )

        screen_usecases[screen_name] = usecases
        all_usecases.update(usecases)

    # Import only the types needed by main.dart.
    imported_ids = {
        adapter["id"],
        *[screen["id"] for screen in screens],
        *all_usecases,
    }

    imports = sorted(
        _path(cid, package) for cid in imported_ids
    )

    lines = ["import 'package:flutter/material.dart';"]

    if provider == "sqlite3":
        lines.extend([
            "import 'package:sqlite3/sqlite3.dart';",
            "import 'package:path/path.dart' as p;",
            "import 'package:path_provider/path_provider.dart';",
        ])

    if uses_mapbox:
        lines.append(
            "import 'package:mapbox_maps_flutter/mapbox_maps_flutter.dart';"
        )

    lines.extend(
        f"import '{uri}';" for uri in imports
    )

    lines.append("")

    if provider == "sqlite3":
        lines.extend([
            "Future<void> main() async {",
            "  WidgetsFlutterBinding.ensureInitialized();",
            "",
            "  final directory = await getApplicationSupportDirectory();",
            "  final databasePath = p.join(directory.path, 'app.db');",
            "  final database = sqlite3.open(databasePath);",
            f"  final repository = {adapter_name}(database);",
        ])

    else:
        lines.extend([
            "void main() {",
            "  WidgetsFlutterBinding.ensureInitialized();",
        ])

        if uses_mapbox:
            lines.extend([
                "  const mapboxToken = String.fromEnvironment('MAPBOX_ACCESS_TOKEN');",
                "  if (mapboxToken.isEmpty) {",
                "    throw StateError('MAPBOX_ACCESS_TOKEN is required');",
                "  }",
                "  MapboxOptions.setAccessToken(mapboxToken);",
            ])

        lines.extend([
            "  const baseUrl = String.fromEnvironment('TAXICAT_API_URL');",
            "  if (baseUrl.isEmpty) {",
            "    throw StateError('TAXICAT_API_URL is required');",
            "  }",
            f"  final repository = {adapter_name}(baseUrl);",
        ])

    lines.extend([
        "",
        "  runApp(MaterialApp(",
        "    debugShowCheckedModeBanner: false,",
        f"    title: {json.dumps(package)},",
        f"    initialRoute: '{entry_route}',",
        "    routes: {",
    ])

    for route, screen_name in sorted(routes.items()):
        arguments = []

        for cid in screen_usecases[screen_name]:
            usecase_name = _class_name(cid, "application")

            arguments.append(
                f"{_variable(usecase_name)}: "
                f"{usecase_name}(repository)"
            )

        if arguments:
            constructor = (
                f"{screen_name}("
                + ", ".join(arguments)
                + ")"
            )
        else:
            constructor = f"{screen_name}()"

        lines.append(
            f"      '{route}': (context) => {constructor},"
        )

    lines.extend([
        "    },",
        "  ));",
        "}",
        "",
    ])

    main = output / "lib" / "main.dart"

    if not main.is_file():
        raise BootstrapError(
            "Missing Flutter template lib/main.dart"
        )


    original = main.read_text(encoding="utf-8")

    is_flutter_template = (
        "class MyApp" in original
        and "class MyHomePage" in original
    )

    is_cidd_bootstrap = (
        "WidgetsFlutterBinding.ensureInitialized();" in original
        and "runApp(MaterialApp(" in original
        and "final repository =" in original
    )

    # An existing CIDD bootstrap may only be replaced inside
    # the isolated assembly output, never in the source project.
    parts = output.resolve().parts
    is_assembly_output = (
        ".cidd" in parts
        and "assembled" in parts
        and parts.index(".cidd") + 1 < len(parts)
        and parts[parts.index(".cidd") + 1] == "assembled"
    )

    if not is_flutter_template and not (
        is_cidd_bootstrap and is_assembly_output
    ):
        raise BootstrapError(
            "Unsupported main.dart: expected Flutter template "
            "or an existing CIDD bootstrap inside assembly output"
        )

    # Preserve the legacy bootstrap safety rule:
    # remove only the known default Flutter widget test.
    removed = []

    for rel in (
        "test/widget_test.dart",
        "flutter/test/widget_test.dart",
    ):
        test_file = output / rel

        if not test_file.is_file():
            continue

        content = test_file.read_text(encoding="utf-8")

        if (
            "MyApp(" in content
            and "package:flutter_test/flutter_test.dart"
            in content
        ):
            test_file.unlink()
            removed.append(rel)
        elif "MyApp(" in content:
            raise BootstrapError(
                f"Unsupported template test: {rel}"
            )

    main.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

    return {
        "status": "PASS",
        "main": "lib/main.dart",
        "entrypoint": f"presentation.{entry_name}",
        "routes": routes,
        "repository_adapter": adapter["id"],
        "use_cases": sorted(all_usecases),
        "template_tests_removed": removed,
        "mode": "windows-native-sqlite3-multiscreen",
    }


def _bootstrap_flutter_http(
    graph: dict,
    output: Path,
    package: str,
) -> dict:
    """Deterministic Flutter bootstrap for one HTTP repository."""

    contracts = graph["contracts"]
    entries = {c["id"]: c for c in contracts}

    screens = [
        c for c in contracts
        if c["id"].startswith("presentation.")
    ]
    adapters = [
        c for c in contracts
        if c["id"].startswith("infrastructure.")
    ]

    if len(screens) != 1 or len(adapters) != 1:
        raise BootstrapError(
            "HTTP bootstrap requires one screen and one adapter"
        )

    screen = screens[0]
    adapter = adapters[0]
    mapbox = mapbox_configuration(screen)

    adapter_spec = json.loads(adapter["specification"])
    if adapter_spec.get("provider") != "http":
        raise BootstrapError("Expected HTTP adapter")

    adapter_name = _class_name(adapter["id"], "infrastructure")
    screen_name = _class_name(screen["id"], "presentation")

    adapter_dependencies = {
        d["id"] for d in adapter.get("dependencies", [])
    }

    usecases = [
        d["id"] for d in screen.get("dependencies", [])
        if d["id"].startswith("application.")
    ]

    if not usecases:
        raise BootstrapError("HTTP screen requires use cases")

    for cid in usecases:
        if cid not in entries:
            raise BootstrapError(f"Missing use case: {cid}")

        repo_deps = [
            d["id"]
            for d in entries[cid].get("dependencies", [])
            if d["id"].startswith("domain.")
            and d["id"].endswith("Repository")
        ]

        if len(repo_deps) != 1 or repo_deps[0] not in adapter_dependencies:
            raise BootstrapError(
                f"{cid}: incompatible repository dependency"
            )

    imported_ids = {
        adapter["id"],
        screen["id"],
        *usecases,
    }

    imports = sorted(
        _path(cid, package) for cid in imported_ids
    )

    if mapbox is not None:
        imports.append(
            "package:mapbox_maps_flutter/mapbox_maps_flutter.dart"
        )

    lines = [
        "import 'package:flutter/material.dart';",
        *[f"import '{uri}';" for uri in imports],
        "",
        "void main() {",
        "  WidgetsFlutterBinding.ensureInitialized();",
        *(
            [
                "",
                "  const mapboxToken = String.fromEnvironment('MAPBOX_ACCESS_TOKEN');",
                "  if (mapboxToken.isEmpty) {",
                "    throw StateError('MAPBOX_ACCESS_TOKEN is required');",
                "  }",
                "  MapboxOptions.setAccessToken(mapboxToken);",
            ]
            if mapbox is not None
            else []
        ),
        "",
        "  const baseUrl = String.fromEnvironment('TAXICAT_API_URL');",
        "  if (baseUrl.isEmpty) {",
        "    throw StateError('TAXICAT_API_URL is required');",
        "  }",
        f"  final repository = {adapter_name}(baseUrl);",
        "",
        "  runApp(MaterialApp(",
        "    debugShowCheckedModeBanner: false,",
        f"    title: {json.dumps(package)},",
        f"    home: {screen_name}(",
    ]

    for cid in usecases:
        name = _class_name(cid, "application")
        lines.append(
            f"      {_variable(name)}: {name}(repository),"
        )

    lines.extend([
        "    ),",
        "  ));",
        "}",
    ])

    main_file = output / "lib" / "main.dart"
    main_file.parent.mkdir(parents=True, exist_ok=True)

    main_file.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    return {
        "status": "PASS",
        "entrypoint": screen["id"],
        "repository_adapter": adapter["id"],
        "mode": "flutter-http-single-screen",
    }



def _bootstrap_flutter_inbound_http(
    graph: dict,
    output: Path,
    package: str,
    config: dict,
) -> dict:
    """Bootstrap one native sqlite3 app and its externally supplied HTTP adapter.

    This mode wires a pre-existing adapter deterministically. It does NOT
    generate that adapter or claim that an LLM worker implemented it.
    """
    api = config.get("api")
    if not isinstance(api, dict) or api.get("transport") != "http":
        raise BootstrapError("HTTP server configuration requires api.transport: http")

    class_name = api.get("implementation_class")
    relative_path = api.get("implementation_path")
    port = api.get("port", 8080)
    if not isinstance(class_name, str) or not re.fullmatch(r"[A-Z][A-Za-z0-9_]*", class_name):
        raise BootstrapError("api.implementation_class must be a Dart class name")
    if not isinstance(relative_path, str) or not re.fullmatch(
        r"lib/[a-z][a-z0-9_]*(?:/[a-z][a-z0-9_]*)*\.dart", relative_path
    ):
        raise BootstrapError("api.implementation_path must be a safe lib/...dart path")
    if type(port) is not int or not 1 <= port <= 65535:
        raise BootstrapError("api.port must be between 1 and 65535")
    if not (output / relative_path).is_file():
        raise BootstrapError(f"HTTP adapter source not present: {relative_path}")

    # The existing sqlite3 bootstrap validates the sealed graph and generates
    # the main entrypoint. We only add the declared HTTP composition root.
    result = _bootstrap_flutter_legacy(graph, output, package)
    main_file = output / "lib" / "main.dart"
    main = main_file.read_text(encoding="utf-8")
    marker = "  runApp(MaterialApp("
    if main.count(marker) != 1:
        raise BootstrapError("Unexpected Flutter bootstrap layout")
    import_statement = f"import 'package:{package}/{relative_path[4:]}';"
    main = import_statement + "\n" + main
    startup = (
        f"  final httpServer = {class_name}(database: database, repository: repository);\n"
        f"  await httpServer.start(port: {port});\n\n"
    )
    main = main.replace(marker, startup + marker, 1)
    main_file.write_text(main, encoding="utf-8")
    result["mode"] = "windows-native-sqlite3-inbound-http"
    result["http_adapter"] = relative_path
    result["http_port"] = port
    return result

def bootstrap_flutter(
    graph: dict,
    output: Path,
    package: str,
) -> dict:
    # Opt-in: without the explicit adapter declaration the legacy modes stay unchanged.
    config_path = output / "api-routes.yaml"
    if config_path.is_file():
        import yaml
        try:
            config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise BootstrapError("Invalid api-routes.yaml") from exc
        if not isinstance(config, dict):
            raise BootstrapError("api-routes.yaml must contain a mapping")
        api = config.get("api")
        if isinstance(api, dict) and "implementation_class" in api:
            return _bootstrap_flutter_inbound_http(graph, output, package, config)


    screens = [
        contract
        for contract in graph["contracts"]
        if contract["id"].startswith("presentation.")
    ]

    # Multi-screen composition takes precedence over
    # single-screen HTTP and legacy bootstrap modes.
    if len(screens) > 1:
        return _bootstrap_flutter_multiscreen(
            graph, output, package
        )

    adapters = [
        contract
        for contract in graph["contracts"]
        if contract["id"].startswith("infrastructure.")
    ]

    if len(adapters) == 1:
        try:
            adapter_spec = json.loads(adapters[0]["specification"])
        except (ValueError, TypeError, KeyError) as exc:
            raise BootstrapError(
                "Invalid infrastructure specification"
            ) from exc

        if adapter_spec.get("provider") == "http":
            return _bootstrap_flutter_http(
                graph, output, package
            )

    return _bootstrap_flutter_legacy(
        graph, output, package
    )
