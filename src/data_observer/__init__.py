"""Synthetic data-contract and observability reference implementation."""

from .contract import ContractError, DataContract, load_contract
from .engine import evaluate
from .models import CheckResult, CheckStatus, ValidationReport

__all__ = [
    "CheckResult",
    "CheckStatus",
    "ContractError",
    "DataContract",
    "ValidationReport",
    "evaluate",
    "load_contract",
]

__version__ = "0.1.0"
