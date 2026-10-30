from pathlib import Path
import pytest
from cidd.engine.generation import GenerationError
from cidd.engine.recover import _package, _sha


def test_recovery_hash_is_stable():
    assert _sha(b'abc') == 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'


def test_package_name_from_pubspec(tmp_path: Path):
    (tmp_path / 'pubspec.yaml').write_text('name: todo\n', encoding='utf-8')
    assert _package(tmp_path) == 'todo'


def test_invalid_package_rejected(tmp_path: Path):
    (tmp_path / 'pubspec.yaml').write_text('name: Not-A-Dart-Package\n', encoding='utf-8')
    with pytest.raises(GenerationError):
        _package(tmp_path)
