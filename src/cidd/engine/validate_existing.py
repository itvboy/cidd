
"""Validate an existing CIDD assembly without calling an LLM."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path, PurePosixPath, PureWindowsPath

from cidd.engine.assembly import _run_command


class ExistingValidationError(ValueError):
    pass


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def safe_path(value: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ExistingValidationError("Invalid source path")

    normalized = value.replace("\\", "/")
    posix = PurePosixPath(normalized)
    windows = PureWindowsPath(value)

    if (
        posix.is_absolute()
        or windows.is_absolute()
        or ".." in posix.parts
        or "." in normalized.split("/")
        or "//" in normalized
        or not normalized.startswith("lib/")
        or not normalized.endswith(".dart")
    ):
        raise ExistingValidationError(f"Unsafe path: {value}")

    return Path(normalized)


def validate_existing(
    graph_path: Path,
    assembly: Path,
    output: Path,
    source_run: Path | None = None,
) -> dict:
    graph = read_json(graph_path)
    historical_report = read_json(
        assembly / "cidd-assembly-report.json"
    )

    fingerprint = graph.get("fingerprint")

    if not fingerprint or historical_report.get(
        "graph_fingerprint"
    ) != fingerprint:
        raise ExistingValidationError("Graph fingerprint mismatch")

    contracts = graph.get("contracts", [])
    records = historical_report.get("contracts", [])
    ids = [c["id"] for c in contracts]

    if (
        not ids
        or len(ids) != len(set(ids))
        or len(records) != len(ids)
        or {r.get("id") for r in records} != set(ids)
    ):
        raise ExistingValidationError(
            "Contract inventory mismatch"
        )

    expected = {"lib/main.dart"}

    for record in records:
        if record.get("status") != "ASSEMBLED":
            raise ExistingValidationError(
                f"Unassembled contract: {record.get('id')}"
            )

        rel = safe_path(record["path"]).as_posix()

        if rel in expected:
            raise ExistingValidationError(
                f"Duplicate source path: {rel}"
            )

        expected.add(rel)

    actual = {
        p.relative_to(assembly).as_posix()
        for p in (assembly / "lib").rglob("*.dart")
    }

    if actual != expected:
        raise ExistingValidationError(
            f"Source inventory mismatch: {sorted(actual ^ expected)}"
        )

    if output.exists():
        raise ExistingValidationError(
            f"Output already exists: {output}"
        )

    if source_run is not None:
        manifest = read_json(source_run / "manifest.json")
        if manifest.get("graph_fingerprint") != fingerprint:
            raise ExistingValidationError(
                "Source run fingerprint mismatch"
            )
        previous = {
            item["id"]: item
            for item in manifest["results"]
        }
        if len(previous) != len(ids) or set(previous) != set(ids):
            raise ExistingValidationError(
                "Source run inventory mismatch"
            )
    else:
        previous = {}

    changes = []

    for record in records:
        cid = record["id"]
        assembled = assembly / safe_path(record["path"])
        new_hash = sha256(assembled)

        origin_hash = None
        status = "ORIGIN_NOT_VERIFIED"

        if source_run is not None:
            layer, name = cid.split(".", 1)
            source = source_run / layer / f"{name}.dart"
            prior = previous[cid]

            if prior.get("status") not in ("GENERATED", "REUSED"):
                raise ExistingValidationError(
                    f"Unsupported origin for {cid}"
                )

            if not source.is_file():
                raise ExistingValidationError(
                    f"Missing original source for {cid}"
                )

            origin_hash = sha256(source)
            declared_hash = prior.get("source_sha256")

            if declared_hash is None:
                origin_integrity = "UNVERIFIABLE_LEGACY"
            elif declared_hash == origin_hash:
                origin_integrity = "VERIFIED"
            else:
                raise ExistingValidationError(
                    f"Origin integrity mismatch for {cid}"
                )

            # Assembly can legitimately transform source imports.
            # Differences are evidence, not automatic proof
            # of manual intervention.
            status = (
                "DIFFERENT_FROM_GENERATED"
                if new_hash != origin_hash
                else "IDENTICAL_TO_GENERATED"
            )

        changes.append({
            "id": cid,
            "assembled_sha256": new_hash,
            "generated_sha256": origin_hash,
            "comparison": status,
            "origin_integrity": (
                origin_integrity
                if source_run is not None
                else "NOT_VERIFIED"
            ),
        })

    shutil.copytree(assembly, output)

    flutter = shutil.which("flutter")
    if flutter is None:
        raise ExistingValidationError(
            "Flutter executable not found"
        )

    pub_get = _run_command(
        [flutter, "pub", "get"], output
    )

    analyzer = (
        _run_command(
            [
                flutter,
                "analyze",
                "--no-pub",
                "--no-fatal-infos",
            ],
            output,
        )
        if pub_get["status"] == "PASS"
        else {
            "status": "BLOCKED",
            "diagnostic": "flutter pub get failed",
        }
    )

    report = dict(historical_report)
    report["pub_get"] = pub_get
    report["analyzer"] = analyzer

    # Preserve historical bootstrap evidence.
    # This command does not rerun the bootstrap.
    report["validation_origin"] = {
        "mode": "EXISTING_ASSEMBLY",
        "historical_report_sha256": sha256(
            assembly / "cidd-assembly-report.json"
        ),
        "source_run": (
            str(source_run.resolve())
            if source_run is not None
            else None
        ),
        "source_comparison": changes,
        "bootstrap_reexecuted": False,
    }

    (output / "cidd-assembly-report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate an existing CIDD assembly"
    )
    parser.add_argument("--graph", required=True, type=Path)
    parser.add_argument("--assembly", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--source-run", type=Path)

    args = parser.parse_args()

    try:
        report = validate_existing(
            args.graph,
            args.assembly,
            args.output,
            args.source_run,
        )
    except (ExistingValidationError, OSError, ValueError) as exc:
        parser.exit(1, f"Validation error: {exc}\n")

    print("Pub get:", report["pub_get"]["status"])
    print("Analyzer:", report["analyzer"]["status"])
    print("Bootstrap:", report["bootstrap"]["status"])
    print("Output:", args.output)

    if (
        report["pub_get"]["status"] != "PASS"
        or report["analyzer"]["status"] != "PASS"
        or report["bootstrap"]["status"] != "PASS"
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
