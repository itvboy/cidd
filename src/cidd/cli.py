
import argparse
from pathlib import Path

from cidd.engine.templates import create_project
from cidd.contracts.materializer import build_graph, write_graph
from cidd.contracts.expander import expand_repository_contracts
from cidd.providers.factory import create_provider
from cidd.providers.base import LLMProviderError
from cidd.engine.generation import generate_graph, GenerationError
from cidd.genome.parser import GenomeError, load_genome
from cidd.genome.validator import validate_genome

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
    graph_command.add_argument("--model", default="muse-glimmer")

    generate_command = commands.add_parser("generate", help="Generate staged sources from a sealed graph")
    generate_command.add_argument("--graph", type=Path, default=Path(".cidd/contract-graph.json"))
    generate_command.add_argument("--output", type=Path, default=Path(".cidd/generated-runs"))
    generate_command.add_argument("--model", default="muse-glimmer")

    args = parser.parse_args()

    if args.command == "new-project":
        repository_root = Path(__file__).resolve().parents[2]

        try:
            project = create_project(
                name=args.name,
                template=args.template,
                templates_dir=repository_root / "templates",
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
            expanded, usage = expand_repository_contracts(genome, create_provider(model=args.model))
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
        try:
            report = generate_graph(args.graph, args.output, create_provider(model=args.model))
        except (GenerationError, OSError, ValueError) as error:
            print(f"[FAIL] {error}")
            raise SystemExit(1) from error
        for item in report["results"]:
            print(f"[{item['status']}] {item['id']} input={item['input_tokens']} output={item['output_tokens']}")
        print(f"Tokens: input={report['input_tokens']} output={report['output_tokens']}")
        print(f"Staging: {report['run_dir']}")
        if any(item["status"] != "GENERATED" for item in report["results"]):
            raise SystemExit(1)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
