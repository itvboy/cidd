import json
from pathlib import Path

from cidd.contracts.materializer import build_graph, write_graph
from cidd.engine.snapshot import promote
from cidd.engine.snapshot_selective import generate_from_snapshot
from cidd.engine.generation import generate_graph
from cidd.providers.base import LLMProvider, LLMResponse


class CountingProvider(LLMProvider):
    def __init__(self):
        self.calls = 0

    def generate(self, system_prompt, user_prompt):
        self.calls += 1
        return LLMResponse(
            content="class Todo {}",
            input_tokens=11,
            output_tokens=3,
        )


def create_graph(tmp_path):
    genome = {
        "genome": "0.1",
        "project": {
            "name": "todo",
            "template": "flutter",
            "language": "dart",
        },
        "domain": {
            "entities": [
                {
                    "name": "Todo",
                    "fields": [
                        {"name": "id", "type": "int"},
                    ],
                },
            ],
        },
        "application": {"use_cases": []},
        "infrastructure": {"persistence": []},
        "presentation": {"framework": "flutter", "screens": []},
    }

    graph = tmp_path / "graph.json"
    write_graph(build_graph(genome), graph)
    return graph


def create_snapshot(tmp_path, graph):
    assembly = tmp_path / "assembly"

    source = assembly / "lib/domain/todo.dart"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("class Todo {}\n", encoding="utf-8")

    main = assembly / "lib/main.dart"
    main.write_text("void main() {}\n", encoding="utf-8")

    graph_data = json.loads(graph.read_text(encoding="utf-8"))

    report = {
        "graph_fingerprint": graph_data["fingerprint"],
        "package": "todo",
        "contracts": [
            {
                "id": "domain.Todo",
                "status": "ASSEMBLED",
                "path": "lib/domain/todo.dart",
            },
        ],
        "pub_get": {"status": "PASS"},
        "bootstrap": {"status": "PASS"},
        "analyzer": {"status": "PASS"},
    }

    (assembly / "cidd-assembly-report.json").write_text(
        json.dumps(report),
        encoding="utf-8",
    )

    snapshot = tmp_path / "snapshot"

    promote(
        graph_path=graph,
        assembly=assembly,
        output=snapshot,
    )

    return snapshot


def test_unchanged_snapshot_uses_zero_llm_calls(tmp_path):
    graph = create_graph(tmp_path)
    snapshot = create_snapshot(tmp_path, graph)
    provider = CountingProvider()

    result = generate_from_snapshot(
        graph,
        snapshot,
        tmp_path / "runs",
        provider,
    )

    assert provider.calls == 0
    assert len(result["results"]) == 1
    assert result["results"][0]["status"] == "REUSED"
    assert result["input_tokens"] == 0
    assert result["output_tokens"] == 0


def test_full_generation_invokes_worker(tmp_path):
    graph = create_graph(tmp_path)
    provider = CountingProvider()

    result = generate_graph(
        graph,
        tmp_path / "runs",
        provider,
    )

    assert provider.calls == 1
    assert result["results"][0]["status"] == "GENERATED"
    assert result["input_tokens"] == 11
    assert result["output_tokens"] == 3


from unittest.mock import patch

from cidd import cli


def test_cli_force_ignores_active_snapshot(tmp_path):
    graph = create_graph(tmp_path)
    snapshot = create_snapshot(tmp_path, graph)

    project = tmp_path / "project"
    project.mkdir()

    graph_dir = project / ".cidd"
    graph_dir.mkdir()

    graph_target = graph_dir / "contract-graph.json"
    graph_target.write_bytes(graph.read_bytes())

    snapshot_target = graph_dir / "snapshots" / "baseline"
    import shutil
    shutil.copytree(snapshot, snapshot_target)

    (graph_dir / "active-snapshot.json").write_text(
        json.dumps({
            "schema": "cidd.active-snapshot/0.1",
            "snapshot": "baseline",
        }),
        encoding="utf-8",
    )

    provider = CountingProvider()

    with (
        patch(
            "sys.argv",
            [
                "cidd",
                "generate",
                "--graph", str(graph_target),
                "--output", str(tmp_path / "forced-runs"),
                "--force",
            ],
        ),
        patch("cidd.cli.create_provider", return_value=provider),
        patch(
            "cidd.engine.snapshot_selector.select_active_snapshot",
            side_effect=AssertionError(
                "--force must not inspect the active snapshot"
            ),
        ),
    ):
        cli.main()

    assert provider.calls == 1
    runs = list((tmp_path / "forced-runs").iterdir())
    assert len(runs) == 1

    manifest = json.loads(
        (runs[0] / "manifest.json").read_text(encoding="utf-8")
    )

    assert manifest["generation_mode"] == "FORCED"

def test_cli_automatically_reuses_active_snapshot(tmp_path):
    import shutil
    from unittest.mock import patch

    from cidd import cli

    graph = create_graph(tmp_path)
    snapshot = create_snapshot(tmp_path, graph)

    project = tmp_path / "project"
    graph_dir = project / ".cidd"
    graph_dir.mkdir(parents=True)

    graph_target = graph_dir / "contract-graph.json"
    graph_target.write_bytes(graph.read_bytes())

    snapshot_target = graph_dir / "snapshots" / "baseline"
    shutil.copytree(snapshot, snapshot_target)

    (graph_dir / "active-snapshot.json").write_text(
        json.dumps({
            "schema": "cidd.active-snapshot/0.1",
            "snapshot": "baseline",
        }),
        encoding="utf-8",
    )

    provider = CountingProvider()

    with (
        patch("sys.argv", [
            "cidd",
            "generate",
            "--graph", str(graph_target),
            "--output", str(tmp_path / "incremental-runs"),
        ]),
        patch("cidd.cli.create_provider", return_value=provider),
    ):
        cli.main()

    assert provider.calls == 0

    runs = list((tmp_path / "incremental-runs").iterdir())
    assert len(runs) == 1

    manifest = json.loads(
        (runs[0] / "manifest.json").read_text(encoding="utf-8")
    )

    assert manifest["generation_mode"] == "INCREMENTAL"

    assert len(manifest["results"]) == 1
    assert manifest["results"][0]["status"] == "REUSED"
    assert manifest["input_tokens"] == 0
    assert manifest["output_tokens"] == 0

def test_forced_generation_failure_preserves_snapshot(tmp_path):
    import hashlib

    class FailingProvider(LLMProvider):
        def __init__(self):
            self.calls = 0

        def generate(self, system_prompt, user_prompt):
            self.calls += 1
            raise RuntimeError("Simulated LLM failure")

    graph = create_graph(tmp_path)
    snapshot = create_snapshot(tmp_path, graph)

    manifest_path = snapshot / "snapshot.json"
    original_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()

    provider = FailingProvider()

    result = generate_graph(
        graph,
        tmp_path / "forced-runs",
        provider,
    )

    assert provider.calls == 1
    assert result["results"][0]["status"] == "FAILED"

    assert hashlib.sha256(
        manifest_path.read_bytes()
    ).hexdigest() == original_hash

    from cidd.engine.snapshot import verify
    verify(snapshot)
