"""Real end-to-end worker smoke test. No generated files are written."""
from cidd.contracts.sealed import SealedContract
from cidd.providers.ollama import OllamaProvider
from cidd.workers.isolated import IsolatedWorker

provider = OllamaProvider(model="muse-glimmer")
worker = IsolatedWorker(provider)
contract = SealedContract(
    contract_id="domain.ride",
    language="python",
    specification=(
        "Implement a Python dataclass named Ride. Fields: "
        "id: int, passenger_id: int, driver_id: int | None = None. "
        "Use standard library only."
    ),
)
result = worker.generate(contract)
print(result.response.content)
print(f"\nContract: {result.contract_id}")
print(f"Input tokens: {result.response.input_tokens}")
print(f"Output tokens: {result.response.output_tokens}")
