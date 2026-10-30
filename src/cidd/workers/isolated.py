"""Stateless invocation. No tools, no repository, no arbitrary file access."""
from dataclasses import dataclass
from cidd.contracts.sealed import SealedContract
from cidd.providers.base import LLMProvider, LLMResponse


@dataclass(frozen=True)
class WorkerResult:
    contract_id: str
    response: LLMResponse


class IsolatedWorker:
    def __init__(self, provider: LLMProvider):
        self._provider = provider

    def generate(self, contract: SealedContract) -> WorkerResult:
        if not isinstance(contract, SealedContract):
            raise TypeError("A SealedContract is required")
        system_prompt = ("""You are an expert code generator.

            Implement exactly one software contract using the provided
            specification, public interfaces, and implementation skill.

            Rules:
            - Follow the contract exactly.
            - Preserve required public names, constructors, and signatures.
            - Use only declared dependencies.
            - Do not invent missing classes, methods, or imports.
            - Implement all specified behavior.
            - Do not invent import paths or package names.
            - Use only explicitly provided import mappings.
            - Do not generate imports for dependencies without a provided mapping.
            - Return only valid source code, without Markdown or explanations."""
        )
        parts = [
            f"CONTRACT ID: {contract.contract_id}",
            f"LANGUAGE: {contract.language}",
            f"SPECIFICATION:\n{contract.specification}",
        ]
        if contract.skill:
            parts.append(f"GENERATION SKILL:\n{contract.skill}")
        parts.append("DEPENDENCY INTERFACES:")
        if contract.dependencies:
            parts.extend(f"[{d.contract_id}]\n{d.interface}" for d in contract.dependencies)
        else:
            parts.append("None")
        response = self._provider.generate(system_prompt, "\n\n".join(parts))
        return WorkerResult(contract_id=contract.contract_id, response=response)
