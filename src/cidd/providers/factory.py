"""Construct providers from configuration without coupling to the engine."""
from .base import LLMProvider
from .ollama import OllamaProvider


def create_provider(
    provider: str = "ollama", *, model: str = "muse-glimmer", **options: object
) -> LLMProvider:
    if provider.lower() == "ollama":
        return OllamaProvider(model=model, **options)
    raise ValueError(f"Unsupported LLM provider: {provider}")
