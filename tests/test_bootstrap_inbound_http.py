"""Regression tests for the opt-in inbound HTTP bootstrap."""
import json
from pathlib import Path

import pytest

from cidd.engine.bootstrap import bootstrap_flutter, BootstrapError


def _contract(cid, deps=(), spec='{}'):
    return {'id': cid, 'dependencies': [{'id': d} for d in deps], 'specification': spec}


def _graph():
    return {'contracts': [
        _contract('presentation.TaxiCatServerView', ('application.ListAvailableRides',)),
        _contract('application.ListAvailableRides', ('domain.RideRepository',)),
        _contract('domain.RideRepository'),
        _contract('infrastructure.RideDatabase', ('domain.RideRepository',), json.dumps({'provider': 'sqlite3'})),
    ]}


def _project(tmp_path: Path):
    lib = tmp_path / 'lib'
    lib.mkdir()
    (lib / 'main.dart').write_text('class MyApp {}\nclass MyHomePage {}\n', encoding='utf-8')
    return lib


def test_inbound_http_bootstrap_starts_before_flutter(tmp_path):
    lib = _project(tmp_path)
    (lib / 'infrastructure').mkdir()
    (lib / 'infrastructure' / 'taxicat_http_server.dart').write_text(
        'class TaxiCatHttpServer {}\n', encoding='utf-8'
    )
    (tmp_path / 'api-routes.yaml').write_text('''api:
  transport: http
  implementation_class: TaxiCatHttpServer
  implementation_path: lib/infrastructure/taxicat_http_server.dart
  port: 8080
''', encoding='utf-8')

    report = bootstrap_flutter(_graph(), tmp_path, 'taxicat_server')
    main = (lib / 'main.dart').read_text(encoding='utf-8')
    assert report['mode'] == 'windows-native-sqlite3-inbound-http'
    assert "import 'package:taxicat_server/infrastructure/taxicat_http_server.dart';" in main
    assert 'final repository = RideDatabase(database);' in main
    assert 'final httpServer = TaxiCatHttpServer(database: database, repository: repository);' in main
    assert 'await httpServer.start(port: 8080);' in main
    assert main.index('await httpServer.start(port: 8080);') < main.index('runApp(')


def test_missing_adapter_fails_closed(tmp_path):
    _project(tmp_path)
    (tmp_path / 'api-routes.yaml').write_text('''api:
  transport: http
  implementation_class: TaxiCatHttpServer
  implementation_path: lib/infrastructure/taxicat_http_server.dart
''', encoding='utf-8')
    with pytest.raises(BootstrapError, match='HTTP adapter source not present'):
        bootstrap_flutter(_graph(), tmp_path, 'taxicat_server')


def test_without_opt_in_preserves_sqlite_mode(tmp_path):
    _project(tmp_path)
    (tmp_path / 'api-routes.yaml').write_text('''api:
  transport: http
  name: TaxiCatHttpApi
  port: 8080
''', encoding='utf-8')
    report = bootstrap_flutter(_graph(), tmp_path, 'taxicat_server')
    assert report['mode'] == 'windows-native-sqlite3-mvp'
    assert 'httpServer' not in (tmp_path / 'lib/main.dart').read_text()


def test_invalid_port_fails_closed(tmp_path):
    lib = _project(tmp_path)
    (lib / 'infrastructure').mkdir()
    (lib / 'infrastructure' / 'taxicat_http_server.dart').write_text('class TaxiCatHttpServer {}')
    (tmp_path / 'api-routes.yaml').write_text('''api:
  transport: http
  implementation_class: TaxiCatHttpServer
  implementation_path: lib/infrastructure/taxicat_http_server.dart
  port: -1
''', encoding='utf-8')
    with pytest.raises(BootstrapError, match='api.port'):
        bootstrap_flutter(_graph(), tmp_path, 'taxicat_server')
