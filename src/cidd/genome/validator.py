
from cidd.genome.parser import GenomeError


REQUIRED_SECTIONS = (
    "genome",
    "project",
    "domain",
    "application",
    "infrastructure",
    "presentation",
)


def validate_genome(genome: dict) -> None:
    sections = tuple(genome.keys())

    if sections != REQUIRED_SECTIONS:
        raise GenomeError(
            "Invalid genome sections or order.\n"
            f"Expected: {REQUIRED_SECTIONS}\n"
            f"Received: {sections}"
        )

    if genome["genome"] != "0.1":
        raise GenomeError(
            "Unsupported genome version"
        )

    project = genome["project"]

    if not isinstance(project, dict):
        raise GenomeError(
            "Section 'project' must be a mapping"
        )

    if not isinstance(project.get("name"), str):
        raise GenomeError(
            "Project name must be a string"
        )

    if not isinstance(project.get("template"), str):
        raise GenomeError(
            "Project template must be a string"
        )

    section_fields = {
        "domain": "entities",
        "application": "use_cases",
        "infrastructure": "persistence",
        "presentation": "screens",
    }

    for section, field in section_fields.items():
        content = genome[section]

        if not isinstance(content, dict):
            raise GenomeError(
                f"Section '{section}' must be a mapping"
            )

        if not isinstance(content.get(field), list):
            raise GenomeError(
                f"'{section}.{field}' must be a list"
            )

    presentation = genome["presentation"]

    if not isinstance(
        presentation.get("framework"), str
    ):
        raise GenomeError(
            "Presentation framework must be a string"
        )
