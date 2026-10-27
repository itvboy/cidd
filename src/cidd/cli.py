
import argparse
from pathlib import Path

from cidd.engine.templates import create_project


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

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
