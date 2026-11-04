
import argparse
import json
from pathlib import Path
import time

from cidd.engine.templates import create_project
from cidd.contracts.materializer import build_graph, write_graph
from cidd.contracts.expander import expand_repository_contracts
from cidd.providers.factory import create_provider
from cidd.providers.base import LLMProviderError
from cidd.engine.generation import generate_graph, GenerationError
from cidd.genome.parser import GenomeError, load_genome
from cidd.genome.validator import validate_genome
from cidd.engine.assembly import assemble, AssemblyError

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="cidd",
        description="Contract Isolated Driven Development",
    )

    parser.add_argument(
        "--version",
        action="version",
        version="CIDD 0.1.0",
    )

    commands = parser.add_subparsers(dest="command")

    new_project = commands.add_parser(
        "new-project",
        help="Create a project from a template",
    )

    new_project.add_argument("name")
    new_project.add_argument(
        "--from-template",
        dest="template",
        required=True,
    )

    commands.add_parser(
        "validate",
        help="Validate the project genome",
    )



    graph_command = commands.add_parser(
        "build-graph", help="Build and seal the contract graph from the genome"
    )
    graph_command.add_argument("--genome", type=Path, default=Path("genome/genome.yaml"))
    graph_command.add_argument("--output", type=Path, default=Path(".cidd/contract-graph.json"))


    graph_command.add_argument(
        "--provider",
        choices=["ollama", "meta"],
        default="ollama",
    )
    graph_command.add_argument("--model", default=None)


    generate_command = commands.add_parser("generate", help="Generate staged sources from a sealed graph")
    generate_command.add_argument("--graph", type=Path, default=Path(".cidd/contract-graph.json"))
    generate_command.add_argument("--output", type=Path, default=Path(".cidd/generated-runs"))


    generate_command.add_argument(
        "--provider",
        choices=["ollama", "meta"],
        default="ollama",
    )
    generate_command.add_argument("--model", default=None)


    generate_command.add_argument(
        "--force",
        action="store_true",
        help="Regenerate all contracts without reusing previous implementations",
    )

    generate_command.add_argument(
        "--snapshot",
        type=Path,
        default=None,
        help="Use a previously validated snapshot as the generation baseline",
    )    


    assemble_command = commands.add_parser(
        "assemble",
        help="Assemble generated contracts into a Flutter project",
    )

    assemble_command.add_argument(
        "--graph",
        type=Path,
        default=Path(".cidd/contract-graph.json"),
    )

    assemble_command.add_argument(
        "--run",
        type=Path,
        required=True,
        help="Generation run directory",
    )

    assemble_command.add_argument(
        "--project",
        type=Path,
        default=Path("."),
    )

    assemble_command.add_argument(
        "--output",
        type=Path,
        default=None,
    )

    assemble_command.add_argument(
        "--no-analyze",
        action="store_true",
        help="Skip Flutter dependency preparation and static analysis",
    )


    args = parser.parse_args()

    if args.command == "new-project":
        package_root = Path(__file__).resolve().parent
        packaged_templates = package_root / "templates"
        repository_templates = package_root.parents[1] / "templates"

        templates_dir = (
            packaged_templates
            if (packaged_templates / args.template).is_dir()
            else repository_templates
        )

        try:
            project = create_project(
                name=args.name,
                template=args.template,
                templates_dir=templates_dir,
                destination_dir=Path.cwd(),
            )
        except (ValueError, FileNotFoundError, FileExistsError) as error:
            parser.error(str(error))

        print(f"Project created: {project}")
    elif args.command == "validate":
        try:
            genome_path = (
                Path.cwd() / "genome" / "genome.yaml"
            )

            genome = load_genome(genome_path)
            validate_genome(genome)

        except GenomeError as error:
            print(f"[FAIL] {error}")
            raise SystemExit(1) from error

        print("CIDD 0.1.0 - Genome Validation")
        print("[PASS] Genome syntax and structure")
        print("Genome valid.")

    elif args.command == "build-graph":
        try:
            genome = load_genome(args.genome)
            validate_genome(genome)


            provider = create_provider(
                provider=args.provider,
                model=args.model,
            )

            expanded, usage = expand_repository_contracts(
                genome,
                provider,
            )

            graph = build_graph(expanded)
            write_graph(graph, args.output)
            for result in usage:
                print(f"[LLM] Expansion input={result.input_tokens} output={result.output_tokens}")
        except (GenomeError, OSError, LLMProviderError) as error:
            print(f"[FAIL] {error}")
            raise SystemExit(1) from error
        print(f"[PASS] Sealed graph: {len(graph.contracts)} contracts")
        print(f"Fingerprint: {graph.fingerprint}")
        print(f"Written: {args.output}")
    elif args.command == "generate":
        start_time = time.perf_counter()
        try:
            if args.force and args.snapshot is not None:
                parser.error("--force and --snapshot cannot be combined")

            from cidd.engine.snapshot_selector import select_active_snapshot

            project_root = args.graph.resolve().parent.parent

            snapshot = None
            if not args.force:
                snapshot = args.snapshot or select_active_snapshot(project_root)

            provider = create_provider(
                provider=args.provider,
                model=args.model,
            )

            if snapshot is None:
                report = generate_graph(
                    args.graph,
                    args.output,
                    provider,
                )
            else:
                from cidd.engine.snapshot_selective import generate_from_snapshot

                report = generate_from_snapshot(
                    args.graph,
                    snapshot,
                    args.output,
                    provider,
                )

            mode = (
                "FORCED" if args.force
                else "INCREMENTAL" if snapshot is not None
                else "FULL"
            )

            report["generation_mode"] = mode

            manifest_path = Path(report["run_dir"]) / "manifest.json"

            manifest = json.loads(
                manifest_path.read_text(encoding="utf-8")
            )

            manifest["generation_mode"] = mode

            manifest_path.write_text(
                json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

            print(f"Generation mode: {mode}")

        except (GenerationError, OSError, ValueError) as error:
            print(f"[FAIL] {error}")
            raise SystemExit(1) from error

        for item in report["results"]:
            print(f"[{item['status']}] {item['id']} input={item['input_tokens']} output={item['output_tokens']}")

        print(f"Tokens: input={report['input_tokens']} output={report['output_tokens']}")

        elapsed_seconds = time.perf_counter() - start_time
        print(f"Time elapsed: {elapsed_seconds:.0f} s")

        print(f"Staging: {report['run_dir']}")

        if any(
            item["status"] not in ("GENERATED", "REUSED")
            for item in report["results"]
        ):
            raise SystemExit(1)

    elif args.command == "assemble":
        output = args.output or (
            args.project / ".cidd" / "assembled" / args.run.name
        )

        try:
            report = assemble(
                graph_path=args.graph,
                run_dir=args.run,
                project=args.project,
                output=output,
                analyze=not args.no_analyze,
            )
        except (AssemblyError, OSError, ValueError) as error:
            print(f"[FAIL] Assembly: {error}")
            raise SystemExit(1) from error

        print(f"Assembly: {output}")

        for item in report["contracts"]:
            print(
                f"[{item['status']}] {item['id']}"
                + (
                    f" - {item['diagnostic']}"
                    if item.get("diagnostic")
                    else ""
                )
            )

        print(f"Bootstrap: {report['bootstrap']['status']}")
        print(f"Pub get: {report['pub_get']['status']}")
        print(f"Analyzer: {report['analyzer']['status']}")
        print(f"Report: {output / 'cidd-assembly-report.json'}")

        contracts_ok = all(
            item["status"] == "ASSEMBLED"
            for item in report["contracts"]
        )

        bootstrap_ok = report["bootstrap"]["status"] == "PASS"

        if args.no_analyze:
            validation_ok = True
        else:
            validation_ok = (
                report["pub_get"]["status"] == "PASS"
                and report["analyzer"]["status"] == "PASS"
            )

        if not (contracts_ok and bootstrap_ok and validation_ok):
            raise SystemExit(1)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
