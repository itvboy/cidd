
"""Meta Model API adapter using the native /v1/responses endpoint."""

import json
import os
import time

from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .base import LLMProvider, LLMProviderError, LLMResponse


class MetaProvider(LLMProvider):
    def __init__(
        self,
        model: str = "muse-wonder-1.0",
        base_url: str = "https://api.meta.ai/v1",
        timeout: float = 300.0,
        reasoning_effort: str = "medium",
        max_output_tokens: int = 16384,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.reasoning_effort = reasoning_effort
        self.max_output_tokens = max_output_tokens

        self.api_key = os.environ.get("MODEL_API_KEY")

        if not self.api_key:
            raise LLMProviderError(
                "MODEL_API_KEY environment variable is not set"
            )

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> LLMResponse:

        payload = {
            "model": self.model,
            "instructions": system_prompt,
            "input": user_prompt,
            "reasoning": {
                "effort": self.reasoning_effort
            },
            "max_output_tokens": self.max_output_tokens,
            "store": False,
        }

        request = Request(
            f"{self.base_url}/responses",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )

        start_ns = time.perf_counter_ns()

        try:
            with urlopen(
                request,
                timeout=self.timeout,
            ) as response:
                result = json.load(response)

        except HTTPError as exc:
            message = exc.read(2048).decode(
                "utf-8",
                errors="replace",
            )

            raise LLMProviderError(
                f"Meta HTTP {exc.code}: {message}"
            ) from exc

        except (URLError, TimeoutError, OSError) as exc:
            raise LLMProviderError(
                f"Cannot reach Meta Model API: {exc}"
            ) from exc

        except (ValueError, UnicodeError) as exc:
            raise LLMProviderError(
                "Meta returned malformed JSON"
            ) from exc

        status = result.get("status")

        if status is not None and status != "completed":
            raise LLMProviderError(
                f"Meta generation incomplete: {status}"
            )

        # Responses API returns text inside output message items.
        content_parts = []

        for item in result.get("output", []):
            if item.get("type") != "message":
                continue

            for part in item.get("content", []):
                if part.get("type") == "output_text":
                    content_parts.append(part.get("text", ""))

        content = "\n".join(content_parts)

        if not content.strip():
            raise LLMProviderError(
                "Meta response contains no output text"
            )

        usage = result.get("usage") or {}

        duration_ns = time.perf_counter_ns() - start_ns

        return LLMResponse(
            content=content,
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
            model=result.get("model", self.model),
            duration_ns=duration_ns,
        )
