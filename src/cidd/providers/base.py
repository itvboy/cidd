"""Provider-neutral interface for isolated language-model generation."""
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class LLMResponse:
    content: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    model: str | None = None
    duration_ns: int | None = None


class LLMProviderError(RuntimeError):
    """A model provider was unavailable or returned an invalid response."""


class LLMProvider(ABC):
    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        """Generate text without granting the model tool or filesystem access."""
