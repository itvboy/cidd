"""Immutable, fully materialized generation input.

The engine owns validation and sealing; a worker cannot mutate its contract.
"""
from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True)
class ContractDependency:
    contract_id: str
    interface: str

    def __post_init__(self):
        if not self.contract_id.strip() or not self.interface.strip():
            raise ValueError("Dependency ID and interface must be nonempty")


@dataclass(frozen=True)
class SealedContract:
    contract_id: str
    language: str
    specification: str
    dependencies: tuple[ContractDependency, ...] = ()
    skill: str = ""

    def __post_init__(self):
        if not all((self.contract_id.strip(), self.language.strip(), self.specification.strip())):
            raise ValueError("contract_id, language and specification are required")
        object.__setattr__(self, "dependencies", tuple(self.dependencies))
        if any(not isinstance(dep, ContractDependency) for dep in self.dependencies):
            raise TypeError("dependencies must contain ContractDependency objects")
