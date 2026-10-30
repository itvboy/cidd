import io
import json
import unittest
from unittest.mock import patch

from cidd.providers.base import LLMProviderError
from cidd.providers.factory import create_provider
from cidd.providers.ollama import OllamaProvider


class MockResponse:
    def __init__(self, payload):
        self.stream = io.BytesIO(json.dumps(payload).encode("utf-8"))

    def __enter__(self):
        return self.stream

    def __exit__(self, *args):
        self.stream.close()


class TestProviders(unittest.TestCase):
    def test_factory(self):
        self.assertIsInstance(create_provider(), OllamaProvider)
        with self.assertRaises(ValueError):
            create_provider("unknown")

    @patch("cidd.providers.ollama.urlopen")
    def test_ollama_response_and_payload(self, mock_urlopen):
        mock_urlopen.return_value = MockResponse({
            "message": {"role": "assistant", "content": "class Ride: pass"},
            "prompt_eval_count": 45,
            "eval_count": 12,
            "model": "muse-glimmer",
            "total_duration": 123456,
        })
        result = create_provider().generate("Only Python code", "Implement Ride")
        self.assertEqual(result.content, "class Ride: pass")
        self.assertEqual((result.input_tokens, result.output_tokens), (45, 12))
        request = mock_urlopen.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(payload["stream"], False)
        self.assertEqual([x["role"] for x in payload["messages"]], ["system", "user"])
        self.assertNotIn("tools", payload)

    @patch("cidd.providers.ollama.urlopen")
    def test_missing_content(self, mock_urlopen):
        mock_urlopen.return_value = MockResponse({"message": {}})
        with self.assertRaises(LLMProviderError):
            OllamaProvider().generate("s", "u")
