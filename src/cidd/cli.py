
import argparse
from pathlib import Path

from cidd.engine.templates import create_project
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

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
