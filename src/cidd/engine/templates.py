
import re
import shutil
from pathlib import Path

TEMPLATE_PROJECT_NAME = "cidd_flutter_template"

EXCLUDED_DIRS = {
    ".git", ".dart_tool", "build",
    ".idea", ".gradle",
}

def create_project(
    name: str,
    template: str,
    templates_dir: Path,
    destination_dir: Path,
) -> Path:
    if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
        raise ValueError(
            "Project name must use lowercase letters, "
            "numbers and underscores, starting with a letter."
        )

    if not re.fullmatch(r"[a-z][a-z0-9_-]*", template):
        raise ValueError("Invalid template name")

    source = templates_dir / template
    destination = destination_dir / name

    if not source.is_dir():
        raise FileNotFoundError(
            f"Template not found: {template}"
        )

    if destination.exists():
        raise FileExistsError(
            f"Project already exists: {destination}"
        )

    shutil.copytree(
        source,
        destination,
        ignore=shutil.ignore_patterns(*EXCLUDED_DIRS),
    )

    genome = destination / "genome" / "genome.yaml"

    if genome.is_file():
        content = genome.read_text(encoding="utf-8")
        genome.write_text(
            content.replace("{{project_name}}", name),
            encoding="utf-8",
        )

    flutter_dir = destination / "flutter"

    pubspec = flutter_dir / "pubspec.yaml"
    if pubspec.is_file():
        content = pubspec.read_text(encoding="utf-8")
        content = content.replace(
            f"name: {TEMPLATE_PROJECT_NAME}",
            f"name: {name}",
            1,
        )
        pubspec.write_text(content, encoding="utf-8")

    for relative in (
        "lib/main.dart",
        "test/widget_test.dart",
    ):
        path = flutter_dir / relative
        if path.is_file():
            content = path.read_text(encoding="utf-8")
            path.write_text(
                content.replace(
                    TEMPLATE_PROJECT_NAME, name
                ),
                encoding="utf-8",
            )

    return destination
