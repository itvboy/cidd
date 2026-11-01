"""Deterministic genome -> sealed contract graph. No model calls."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import hashlib
import re

from cidd.contracts.sealed import ContractDependency, SealedContract
from cidd.skills.registry import resolve_skill
from cidd.genome.parser import GenomeError
from cidd.genome.validator import validate_genome

SECTIONS = (("domain", "entities"), ("application", "use_cases"),
            ("infrastructure", "persistence"), ("presentation", "screens"))

@dataclass(frozen=True)
class ContractGraph:
    contracts: tuple[SealedContract, ...]
    fingerprint: str
    presentation: dict | None = None

    def to_dict(self) -> dict:
        result = {
            "schema": "cidd.contract-graph/0.1",
            "fingerprint": self.fingerprint,
            "contracts": [
                {
                    "id": c.contract_id,
                    "language": c.language,
                    "specification": c.specification,
                    "skill": c.skill,
                    "dependencies": [
                        {
                            "id": d.contract_id,
                            "interface": d.interface,
                        }
                        for d in c.dependencies
                    ],
                }
                for c in self.contracts
            ],
        }
        if self.presentation is not None:
            result["presentation"] = self.presentation
        return result

def _name(entry: dict, location: str) -> str:
    value = entry.get("id", entry.get("name"))
    if not isinstance(value, str) or not value.strip():
        raise GenomeError(f"{location}: expected a nonempty 'id' or 'name'")
    if any(ch.isspace() for ch in value) or '/' in value or '\\' in value:
        raise GenomeError(f"{location}: invalid contract identifier {value!r}")
    return value


# MVP Dart entity public surface: deterministic, no LLM tokens.
_DART_TYPES = {"int": "int", "string": "String", "bool": "bool", "double": "double"}


def _derive_entity_constructor(entry: dict, language: str) -> str:
    """Deterministic named constructor from the already declared entity fields."""
    name = _name(entry, "domain.entities")
    fields = entry["fields"]
    params = []
    for field in fields:
        field_name = field["name"]
        nullable = field.get("nullable", False)
        required = field.get("required", False)
        if "default" in field:
            value = field["default"]
            kind = field["type"].lower()
            if kind == "bool" and type(value) is bool:
                default = "true" if value else "false"
            elif kind == "int" and type(value) is int:
                default = str(value)
            elif kind == "double" and type(value) in (float, int):
                default = str(value)
            elif kind == "string" and type(value) is str:
                default = json.dumps(value, ensure_ascii=False)
            else:
                raise GenomeError(f"domain.{name}.{field_name}: invalid constructor default")
            params.append(f"this.{field_name} = {default}")
        elif required or not nullable:
            params.append(f"required this.{field_name}")
        else:
            params.append(f"this.{field_name}")
    return f"  {name}({{{', '.join(params)}}});"


def derive_entity_interface(entry: dict, language: str) -> str:
    """Render a Dart entity's field interface, not its implementation.

    Reject unsupported or ambiguous types instead of guessing.
    """
    if language.lower() != "dart":
        raise GenomeError("Automatic entity interfaces currently support Dart only")
    entity_name = _name(entry, "domain.entities")
    fields = entry.get("fields")
    if not isinstance(fields, list) or not fields:
        raise GenomeError(f"domain.{entity_name}: fields must be a nonempty list")
    lines = [f"class {entity_name} {{"]
    seen = set()
    for field in fields:
        if not isinstance(field, dict):
            raise GenomeError(f"domain.{entity_name}: invalid field")
        name = field.get("name")
        raw_type = field.get("type")
        if not isinstance(name, str) or not name.isidentifier() or name in seen:
            raise GenomeError(f"domain.{entity_name}: invalid or duplicate field name {name!r}")
        seen.add(name)
        if not isinstance(raw_type, str) or raw_type.lower() not in _DART_TYPES:
            raise GenomeError(f"domain.{entity_name}.{name}: unsupported Dart type {raw_type!r}")
        if not isinstance(field.get("nullable", False), bool):
            raise GenomeError(f"domain.{entity_name}.{name}: nullable must be boolean")
        if not isinstance(field.get("required", False), bool):
            raise GenomeError(f"domain.{entity_name}.{name}: required must be boolean")
        if field.get("nullable", False) and field.get("required", False):
            raise GenomeError(f"domain.{entity_name}.{name}: nullable and required conflict in MVP")
        dart_type = _DART_TYPES[raw_type.lower()] + ("?" if field.get("nullable", False) else "")
        lines.append(f"  final {dart_type} {name};")
    lines.append(_derive_entity_constructor(entry, language))
    lines.append("}")
    return "\n".join(lines)



def _dart_value_type(raw: str, known_entities: set[str], location: str) -> str:
    """Translate the deliberately small MVP genome type system to Dart."""
    if not isinstance(raw, str):
        raise GenomeError(f"{location}: expected a type string")
    value = raw.strip()
    if value.lower() in _DART_TYPES:
        return _DART_TYPES[value.lower()]
    if value in known_entities:
        return value
    if value.startswith("list<") and value.endswith(">"):
        inner = _dart_value_type(value[5:-1].strip(), known_entities, location)
        return f"List<{inner}>"
    raise GenomeError(f"{location}: unsupported Dart type {raw!r}")


def derive_use_case_interface(entry: dict, language: str, known_entities: set[str],
                              repository_names: set[str]) -> str:
    """Produce the minimal, stable public API for a Dart use case.

    The method is synchronous in this MVP, matching the currently sealed
    synchronous TodoRepository signatures. The constructor shape is stated
    as a comment rather than inventing a compilable constructor body.
    """
    if language.lower() != "dart":
        raise GenomeError("Automatic use-case interfaces currently support Dart only")
    name = _name(entry, "application.use_cases")
    params = entry.get("input", {})
    if not isinstance(params, dict):
        raise GenomeError(f"application.{name}: input must be a mapping")
    rendered = []
    for field, raw_type in params.items():
        if not isinstance(field, str) or not field.isidentifier():
            raise GenomeError(f"application.{name}: invalid input name {field!r}")
        dart_type = _dart_value_type(raw_type, known_entities, f"application.{name}.input.{field}")
        rendered.append(f"{dart_type} {field}")
    output = entry.get("output")

    if not isinstance(output, str) or not output.strip():
        raise GenomeError(
            f"application.{name}: output must be a nonempty type string"
        )

    result_type = _dart_value_type(
        output,
        known_entities,
        f"application.{name}.output",
    )

    repository_deps = [x for x in entry.get("depends_on", []) if x in repository_names]
    if len(repository_deps) > 1:
        raise GenomeError(f"application.{name}: ambiguous repository constructor dependencies")
    lines = [f"// CIDD SEALED PUBLIC API: {name}"]
    if repository_deps:
        repository = repository_deps[0].split(".", 1)[1]
        lines.append(f"// Required public constructor: {name}({repository} repository)")
    lines.extend((f"abstract interface class {name} {{",
                  f"  {result_type} execute({', '.join(rendered)});",
                  "}"))
    return "\n".join(lines)


def _derived_interface(identifier: str, entry: dict, layer: str,
                       language: str, known_entities: set[str],
                       repository_names: set[str]) -> str | None:
    if layer == "domain" and isinstance(entry.get("fields"), list):
        return derive_entity_interface(entry, language)
    if layer == "application":
        # Historical genomes may omit output. Do not guess a return type:
        # preserve the legacy contract unless an explicit public interface exists.
        # If another contract depends on it, build_graph still requires a
        # nonempty interface and will fail with the existing actionable error.
        if "output" not in entry:
            return None
        return derive_use_case_interface(entry, language, known_entities, repository_names)
    return None


def _resolve_public_interface(identifier: str, entry: dict, layer: str,
                              language: str, known_entities: set[str],
                              repository_names: set[str]) -> str | None:
    explicit = entry.get("interface")
    derived = _derived_interface(identifier, entry, layer, language,
                                 known_entities, repository_names)
    if derived is not None:
        if explicit is not None and (not isinstance(explicit, str) or
                                     explicit.strip() != derived.strip()):
            raise GenomeError(f"{identifier}: explicit interface disagrees with derived public API")
        return derived
    return explicit

def derive_dependency_type_context(
    dependencies: list[ContractDependency],
    indexed: dict,
    language: str,
) -> str:
    """Resolve public entity types referenced by direct dependency APIs."""

    referenced_interfaces = "\n".join(
        dep.interface for dep in dependencies
    )

    direct_ids = {
        dep.contract_id for dep in dependencies
    }

    resolved = []

    for identifier, (entry, layer) in sorted(indexed.items()):
        if layer != "domain":
            continue

        if not isinstance(entry.get("fields"), list):
            continue

        if identifier in direct_ids:
            continue

        entity_name = identifier.split(".", 1)[1]

        if not re.search(
            rf"\b{re.escape(entity_name)}\b",
            referenced_interfaces,
        ):
            continue

        resolved.append(
            f"[{identifier}]\n"
            + derive_entity_interface(entry, language)
        )

    if not resolved:
        return ""

    return (
        "REFERENCED PUBLIC TYPE DEFINITIONS:\n"
        + "\n\n".join(resolved)
        + "\n\nThese definitions are read-only type information. "
        "Do not redeclare these classes. "
        "Respect exact field names and nullability. "
        "Nullable values must be checked before use as non-null values."
    )

def _presentation_metadata(genome: dict) -> dict | None:
    presentation = genome["presentation"]
    screens = presentation["screens"]

    names = [_name(s, "presentation.screens") for s in screens]
    if len(names) != len(set(names)):
        raise GenomeError("Duplicate presentation screen")

    known = set(names)
    entry = presentation.get("entry_screen")

    if entry is None:
        if len(names) > 1:
            raise GenomeError(
                "Multiple screens require presentation.entry_screen"
            )
        
    elif entry not in known:
        raise GenomeError(f"Unknown entry screen: {entry}")

    assets = presentation.get("assets", [])
    if not isinstance(assets, list):
        raise GenomeError("presentation.assets must be a list")

    paths = set()
    for asset in assets:
        if not isinstance(asset, dict):
            raise GenomeError("Invalid asset declaration")

        path = asset.get("path")
        if (
            not isinstance(path, str)
            or not path.startswith("assets/")
            or "\\" in path
            or ".." in path.split("/")
            or not all(path.split("/"))
        ):
            raise GenomeError(f"Invalid asset path: {path!r}")

        if asset.get("type") != "image" or path in paths:
            raise GenomeError(f"Invalid or duplicate image asset: {path}")

        paths.add(path)

    for screen in screens:
        name = _name(screen, "presentation.screens")
        navigation = screen.get("navigation", {})

        if not isinstance(navigation, dict):
            raise GenomeError(f"{name}: invalid navigation")

        targets = []

        if "on_start" in navigation:
            start = navigation["on_start"]
            if not isinstance(start, dict):
                raise GenomeError(f"{name}: invalid on_start")

            targets.append(start.get("to"))
            delay = start.get("delay_ms", 0)

            if type(delay) is not int or delay < 0:
                raise GenomeError(f"{name}: invalid delay_ms")

        if "actions" in navigation:
            actions = navigation["actions"]
            if not isinstance(actions, list):
                raise GenomeError(f"{name}: invalid actions")

            for action in actions:
                if not isinstance(action, dict):
                    raise GenomeError(f"{name}: invalid action")
                targets.append(action.get("to"))

        if "back" in navigation and type(navigation["back"]) is not bool:
            raise GenomeError(f"{name}: navigation.back must be boolean")

        for target in targets:
            if target not in known:
                raise GenomeError(
                    f"{name}: unknown navigation target {target!r}"
                )

        image = screen.get("image")
        if image is not None and image not in paths:
            raise GenomeError(
                f"{name}: undeclared image asset {image!r}"
            )

    # Preserve the legacy single-screen graph format.
    if not names and not assets:
        return None

    if entry is None and not assets:
        return None

    return {
        "entry_screen": entry or names[0],
        "assets": assets,
    }

def build_graph(genome: dict) -> ContractGraph:
    validate_genome(genome)
    indexed = {}
    for layer, collection in SECTIONS:
        for i, entry in enumerate(genome[layer][collection]):
            where = f"{layer}.{collection}[{i}]"
            if not isinstance(entry, dict):
                raise GenomeError(f"{where}: expected mapping")
            identifier = f"{layer}.{_name(entry, where)}"
            if identifier in indexed:
                raise GenomeError(f"Duplicate contract: {identifier}")
            indexed[identifier] = (entry, layer)

    language = genome["project"]["language"]
    known_entities = {identifier.split(".", 1)[1] for identifier, (_, layer) in indexed.items()
                      if layer == "domain" and isinstance(indexed[identifier][0].get("fields"), list)}
    repository_names = {identifier for identifier, (_, layer) in indexed.items()
                        if layer == "domain" and identifier.endswith("Repository")}

    contracts = []
    for identifier, (entry, layer) in sorted(indexed.items()):
        deps = entry.get("depends_on", [])
        if not isinstance(deps, list) or any(not isinstance(x, str) for x in deps):
            raise GenomeError(f"{identifier}: depends_on must be a list of IDs")
        if len(deps) != len(set(deps)):
            raise GenomeError(f"{identifier}: duplicate dependency")

        if layer == "presentation" and "uses" in entry:
            uses = entry["uses"]

            if not isinstance(uses, list) or any(
                not isinstance(name, str) for name in uses
            ):
                raise GenomeError(
                    f"{identifier}: uses must be a list of use-case names"
                )

            expected = {
                dep.split(".", 1)[1]
                for dep in deps
                if dep.startswith("application.")
            }

            actual = set(uses)

            if len(uses) != len(actual) or actual != expected:
                raise GenomeError(
                    f"{identifier}: uses must match application dependencies. "
                    f"Expected {sorted(expected)}, got {sorted(actual)}"
                )
        
        dependencies = []
        for dep in deps:
            if dep == identifier:
                raise GenomeError(f"{identifier}: self dependency")
            if dep not in indexed:
                raise GenomeError(f"{identifier}: unknown dependency {dep!r}")
            dep_entry, dep_layer = indexed[dep]
            interface = _resolve_public_interface(dep, dep_entry, dep_layer, language,
                                                  known_entities, repository_names)
            if not isinstance(interface, str) or not interface.strip():
                raise GenomeError(f"{identifier}: dependency {dep} requires a nonempty interface")
            dependencies.append(ContractDependency(dep, interface))

        # Resolve public entity types referenced by direct dependency APIs.
        # These are type dependencies, not additional implementation services.
        referenced_interfaces = "\n".join(
            dependency.interface for dependency in dependencies
        )

        existing_ids = {
            dependency.contract_id for dependency in dependencies
        }

        for type_id, (type_entry, type_layer) in sorted(indexed.items()):
            if type_layer != "domain":
                continue

            if not isinstance(type_entry.get("fields"), list):
                continue

            if type_id in existing_ids:
                continue

            type_name = type_id.split(".", 1)[1]

            if not re.search(
                rf"\b{re.escape(type_name)}\b",
                referenced_interfaces,
            ):
                continue

            interface = derive_entity_interface(type_entry, language)

            dependencies.append(
                ContractDependency(type_id, interface)
            )
        language = genome.get("project", {}).get("language")
        if language is None:
            # Framework is not a source language; explicit language avoids guessing.
            raise GenomeError(f"{identifier}: specify 'language' in entry or project")
        if not isinstance(language, str) or not language.strip():
            raise GenomeError(f"{identifier}: language must be nonempty")
        skill = entry.get("skill", "")
        skill = resolve_skill(language, identifier, entry)
        if (
            layer == "infrastructure"
            and language.lower() == "dart"
            and entry.get("provider") == "sqlite3"
        ):
            class_name = identifier.split(".", 1)[1]

            skill += (
                "\n\nSEALED CONSTRUCTION API:\n"
                f"- Required constructor: {class_name}(Database database)\n"
                "- Database is provided by package:sqlite3/sqlite3.dart.\n"
                "- The bootstrap opens the database and passes the Database instance.\n"
                "- Do not replace Database with String, dynamic, or Object.\n"
                "- Do not call sqlite3.open() inside the adapter constructor.\n"
                "- Store and use the provided Database instance.\n"
                "- Initialize the database schema in the constructor.\n"
                "- Execute CREATE TABLE IF NOT EXISTS for every persisted entity.\n"
                "- Complete schema initialization before the constructor returns.\n"
                "- Reopening an existing database must preserve its records.\n"
                "- Do not assume tables already exist.\n"
            )

            api_skill_path = (
                Path(__file__).resolve().parents[1]
                / "skills"
                / "api"
                / "dart"
                / "sqlite3_v3.txt"
            )

            api_skill = api_skill_path.read_text(encoding="utf-8")

            skill += "\n\n" + api_skill

        if not isinstance(skill, str):
            raise GenomeError(f"{identifier}: skill must be a string")

        type_context = derive_dependency_type_context(
            dependencies,
            indexed,
            language,
        )

        if type_context:
            skill = (
                skill + "\n\n" + type_context
                if skill
                else type_context
            )
        
        # Seal the same public API in the owner and every dependent's context.
        effective_entry = dict(entry)
        public_interface = _resolve_public_interface(identifier, entry, layer, language,
                                                     known_entities, repository_names)
        if public_interface is not None:
            effective_entry["interface"] = public_interface
        if layer == "application":
            skill += ("\n- Implement the sealed specification.interface precisely: "
                      "public execute method, parameter types, return type and "
                      "required repository constructor. Do not change synchronous "
                      "methods to Future unless the interface says so.")
        specification = json.dumps(effective_entry, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
        contracts.append(SealedContract(identifier, language, specification,
                                        tuple(dependencies), skill))

    contract_data = [
        {
            "id": c.contract_id,
            "language": c.language,
            "specification": c.specification,
            "skill": c.skill,
            "dependencies": [
                (d.contract_id, d.interface)
                for d in c.dependencies
            ],
        }
        for c in contracts
    ]

    presentation = _presentation_metadata(genome)

    # Keep old single-screen fingerprints unchanged.
    fingerprint_data = (
        contract_data
        if presentation is None
        else {
            "contracts": contract_data,
            "presentation": presentation,
        }
    )

    payload = json.dumps(
        fingerprint_data,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    fingerprint = hashlib.sha256(
        payload.encode("utf-8")
    ).hexdigest()

    return ContractGraph(
        tuple(contracts),
        fingerprint,
        presentation,
    )

def write_graph(graph: ContractGraph, path: Path) -> None:
    """Atomic graph replacement; never touch generated implementation files."""
    path.parent.mkdir(parents=True, exist_ok=True)
    import os
    import tempfile
    tmp = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent,
                                         prefix='.graph-', suffix='.tmp', delete=False) as out:
            tmp = Path(out.name)
            json.dump(graph.to_dict(), out, ensure_ascii=False, indent=2)
            out.write('\n')
        os.replace(tmp, path)
    finally:
        if tmp is not None and tmp.exists():
            tmp.unlink()
