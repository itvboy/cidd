
import json
from pathlib import Path

import pytest

from cidd.engine.validate_existing import (
    ExistingValidationError,
    validate_existing,
)


def make_fixture(tmp_path: Path):
    graph = tmp_path / "graph.json"
    graph.write_text(
        json.dumps({
            "fingerprint": "test123",
            "contracts": [{"id": "domain.Todo"}],
        }),
        encoding="utf-8",
    )

    assembly = tmp_path / "assembly"
    source = assembly / "lib/domain/todo.dart"
    source.parent.mkdir(parents=True)
    source.write_text("class Todo {}\n", encoding="utf-8")

    (assembly / "lib/main.dart").write_text(
        "void main() {}\n", encoding="utf-8"
    )

    report = {
        "graph_fingerprint": "test123",
        "package": "todo",
        "contracts": [{
            "id": "domain.Todo",
            "status": "ASSEMBLED",
            "path": "lib/domain/todo.dart",
        }],
        "bootstrap": {"status": "PASS"},
        "pub_get": {"status": "FAIL"},
        "analyzer": {"status": "FAIL"},
    }

    (assembly / "cidd-assembly-report.json").write_text(
        json.dumps(report),
        encoding="utf-8",
    )

    return graph, assembly


def test_validate_existing_success(tmp_path, monkeypatch):
    graph, assembly = make_fixture(tmp_path)
    output = tmp_path / "validated"

    monkeypatch.setattr(
        "cidd.engine.validate_existing.shutil.which",
        lambda name: "flutter" if name == "flutter" else None,
    )

    def fake_run(command, cwd):
        return {
            "status": "PASS",
            "exit_code": 0,
            "command": command,
        }

    monkeypatch.setattr(
        "cidd.engine.validate_existing._run_command",
        fake_run,
    )

    result = validate_existing(graph, assembly, output)

    assert result["pub_get"]["status"] == "PASS"
    assert result["analyzer"]["status"] == "PASS"
    assert result["validation_origin"]["bootstrap_reexecuted"] is False
    assert (output / "lib/domain/todo.dart").is_file()

    # Historical evidence must remain unchanged.
    historical = json.loads(
        (assembly / "cidd-assembly-report.json").read_text()
    )
    assert historical["analyzer"]["status"] == "FAIL"


def test_rejects_extra_dart_file(tmp_path):
    graph, assembly = make_fixture(tmp_path)

    (assembly / "lib/extra.dart").write_text(
        "class Extra {}\n",
        encoding="utf-8",
    )

    with pytest.raises(
        ExistingValidationError,
        match="inventory",
    ):
        validate_existing(
            graph, assembly, tmp_path / "validated"
        )


def test_rejects_graph_mismatch(tmp_path):
    graph, assembly = make_fixture(tmp_path)

    graph.write_text(
        json.dumps({
            "fingerprint": "different",
            "contracts": [{"id": "domain.Todo"}],
        }),
        encoding="utf-8",
    )

    with pytest.raises(
        ExistingValidationError,
        match="fingerprint",
    ):
        validate_existing(
            graph, assembly, tmp_path / "validated"
        )


def test_never_overwrites_existing_output(tmp_path):
    graph, assembly = make_fixture(tmp_path)

    output = tmp_path / "validated"
    output.mkdir()

    with pytest.raises(
        ExistingValidationError,
        match="already exists",
    ):
        validate_existing(graph, assembly, output)


def test_rejects_unsafe_paths(tmp_path):
    graph, assembly = make_fixture(tmp_path)

    report_path = assembly / "cidd-assembly-report.json"
    report = json.loads(report_path.read_text())

    report["contracts"][0]["path"] = "../outside.dart"
    report_path.write_text(json.dumps(report))

    with pytest.raises(
        ExistingValidationError,
        match="Unsafe",
    ):
        validate_existing(
            graph, assembly, tmp_path / "validated"
        )
