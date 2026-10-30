"""Ollama adapter using the native /api/chat endpoint."""
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .base import LLMProvider, LLMProviderError, LLMResponse


class OllamaProvider(LLMProvider):
    def __init__(
        self,
        model: str = "muse-glimmer",
        #model: str = "qwen3-coder-next",
        base_url: str = "http://localhost:11434",
        timeout: float = 180.0,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def generate(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        payload = {
            "model": self.model,
            "stream": False,
            "think": False,
            "options": {
                "num_ctx": 4096,
            },
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        request = Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                result = json.load(response)
        except HTTPError as exc:
            message = exc.read(1024).decode("utf-8", errors="replace")
            raise LLMProviderError(f"Ollama HTTP {exc.code}: {message}") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise LLMProviderError(f"Cannot reach Ollama at {self.base_url}: {exc}") from exc
        except (ValueError, UnicodeError) as exc:
            raise LLMProviderError("Ollama returned malformed JSON") from exc

        try:
            content = result["message"]["content"]
            if not isinstance(content, str):
                raise TypeError("message.content must be a string")
        except (KeyError, TypeError) as exc:
            raise LLMProviderError("Ollama response is missing message.content") from exc

        return LLMResponse(
            content=content,
            input_tokens=result.get("prompt_eval_count"),
            output_tokens=result.get("eval_count"),
            model=result.get("model", self.model),
            duration_ns=result.get("total_duration"),
        )
