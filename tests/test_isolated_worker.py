from dataclasses import FrozenInstanceError
import pytest
from cidd.contracts.sealed import ContractDependency, SealedContract
from cidd.workers.isolated import IsolatedWorker
from cidd.providers.base import LLMProvider, LLMResponse


class SpyProvider(LLMProvider):
    def __init__(self):
        self.calls = []

    def generate(self, system_prompt, user_prompt):
        self.calls.append((system_prompt, user_prompt))
        return LLMResponse(content="class Ride: pass", input_tokens=20, output_tokens=5)


def test_isolation_and_metrics():
    provider = SpyProvider()
    worker = IsolatedWorker(provider)
    contract = SealedContract("ride", "python", "Implement Ride", (
        ContractDependency("repository", "get_by_id(id) -> Ride"),
    ))
    result = worker.generate(contract)
    assert result.contract_id == "ride"
    assert result.response.input_tokens == 20
    assert "Implement Ride" in provider.calls[0][1]
    assert "get_by_id(id) -> Ride" in provider.calls[0][1]
    assert "repository path" not in provider.calls[0][1]


def test_contract_immutable_and_dependencies_copied():
    deps = [ContractDependency("driver", "class Driver: ...")]

    contract = SealedContract(
        "ride",
        "python",
        "Ride",
        deps,  # type: ignore[arg-type]
    )

    deps.clear()
    assert len(contract.dependencies) == 1

    with pytest.raises(FrozenInstanceError):
        setattr(contract, "specification", "tampered")

def test_no_dependency_code_or_repository_access():
    class ExplodingProvider(LLMProvider):
        def generate(self, system_prompt, user_prompt):
            assert "secret_implementation" not in user_prompt
            assert "authorized interface" in user_prompt
            return LLMResponse(content="ok")
    contract = SealedContract("app", "python", "Implement app", (
        ContractDependency("domain", "authorized interface"),
    ))
    assert IsolatedWorker(ExplodingProvider()).generate(contract).response.content == "ok"
