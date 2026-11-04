
import re


def screen_route(screen_name: str) -> str:
    if not re.fullmatch(r"[A-Z][A-Za-z0-9_]*", screen_name):
        raise ValueError(f"Invalid screen name: {screen_name!r}")

    name = screen_name

    for suffix in ("Screen", "View"):
        if name.endswith(suffix) and len(name) > len(suffix):
            name = name[:-len(suffix)]
            break

    name = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "-", name)
    name = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", "-", name)

    return "/" + name.lower()
