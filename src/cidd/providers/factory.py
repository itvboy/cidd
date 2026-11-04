
"""Construct providers from configuration without coupling to the engine."""

from .base import LLMProvider
from .ollama import OllamaProvider
from .meta import MetaProvider


def create_provider(
    provider: str = "ollama",
    *,
    model: str | None = None,
    **options: object,
) -> LLMProvider:
    provider = provider.lower()

    if provider == "ollama":
        return OllamaProvider(
            model=model or "muse-glimmer",
            **options,
        )

    if provider == "meta":
        return MetaProvider(
            model=model or "muse-wonder-1.0",
            **options,
        )

    raise ValueError(f"Unsupported LLM provider: {provider}")
