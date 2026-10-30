"""Run from project root with an active venv and Ollama running."""

from cidd.providers.factory import create_provider


provider = create_provider("ollama", model="muse-glimmer")
response = provider.generate(
    system_prompt="You are an isolated CIDD code worker. Respond with plain Python code only.",
    user_prompt="Create a Python dataclass named Ride with fields id: int and passenger_id: int.",
)
print(response.content)
print(f"Input tokens: {response.input_tokens}; Output tokens: {response.output_tokens}")
print(f"Model: {response.model}")
