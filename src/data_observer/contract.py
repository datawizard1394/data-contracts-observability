"""Data-contract loading and configuration validation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


SUPPORTED_TYPES = {"string", "integer", "number", "boolean", "date", "datetime"}
SUPPORTED_DISTRIBUTIONS = {"allowed_values", "range", "null_rate"}


class ContractError(ValueError):
    """Raised when a contract is incomplete or internally inconsistent."""


@dataclass(frozen=True)
class FieldSpec:
    name: str
    data_type: str
    nullable: bool = True
    description: str = ""


@dataclass(frozen=True)
class DataContract:
    dataset: str
    version: str
    owner: str
    tier: int
    fields: tuple[FieldSpec, ...]
    checks: dict[str, Any] = field(default_factory=dict)
    slo_target_percent: float = 99.0
    description: str = ""
    synthetic: bool = True

    @property
    def field_names(self) -> tuple[str, ...]:
        return tuple(item.name for item in self.fields)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DataContract":
        required = ("dataset", "version", "owner", "schema")
        missing = [key for key in required if key not in payload]
        if missing:
            raise ContractError(f"Contract is missing keys: {', '.join(missing)}")

        schema = payload["schema"]
        if not isinstance(schema, list) or not schema:
            raise ContractError("'schema' must be a non-empty list")

        fields: list[FieldSpec] = []
        seen: set[str] = set()
        for index, item in enumerate(schema):
            if not isinstance(item, dict) or "name" not in item or "type" not in item:
                raise ContractError(f"schema[{index}] requires 'name' and 'type'")
            name = str(item["name"]).strip()
            data_type = str(item["type"]).lower().strip()
            if not name:
                raise ContractError(f"schema[{index}].name cannot be blank")
            if name in seen:
                raise ContractError(f"Duplicate schema field: {name}")
            if data_type not in SUPPORTED_TYPES:
                raise ContractError(
                    f"Unsupported type '{data_type}' for {name}; "
                    f"expected one of {sorted(SUPPORTED_TYPES)}"
                )
            seen.add(name)
            fields.append(
                FieldSpec(
                    name=name,
                    data_type=data_type,
                    nullable=bool(item.get("nullable", True)),
                    description=str(item.get("description", "")),
                )
            )

        checks = payload.get("checks", {})
        if not isinstance(checks, dict):
            raise ContractError("'checks' must be an object")
        cls._validate_check_references(checks, seen)

        target = float(payload.get("slo", {}).get("target_percent", 99.0))
        if not 0 <= target <= 100:
            raise ContractError("slo.target_percent must be between 0 and 100")
        tier = int(payload.get("tier", 2))
        if tier not in (1, 2, 3):
            raise ContractError("tier must be 1, 2, or 3")

        return cls(
            dataset=str(payload["dataset"]),
            version=str(payload["version"]),
            owner=str(payload["owner"]),
            tier=tier,
            fields=tuple(fields),
            checks=checks,
            slo_target_percent=target,
            description=str(payload.get("description", "")),
            synthetic=bool(payload.get("synthetic", True)),
        )

    @staticmethod
    def _validate_check_references(checks: dict[str, Any], fields: set[str]) -> None:
        freshness = checks.get("freshness")
        if freshness:
            column = freshness.get("timestamp_column")
            if column not in fields:
                raise ContractError(
                    f"Freshness check references unknown field: {column}"
                )
        uniqueness = checks.get("uniqueness", [])
        if not isinstance(uniqueness, list):
            raise ContractError("checks.uniqueness must be a list")
        unknown_unique = [name for name in uniqueness if name not in fields]
        if unknown_unique:
            raise ContractError(
                f"Uniqueness check references unknown fields: {unknown_unique}"
            )
        for index, check in enumerate(checks.get("distribution", [])):
            kind = check.get("kind")
            column = check.get("column")
            if kind not in SUPPORTED_DISTRIBUTIONS:
                raise ContractError(
                    f"distribution[{index}] has unsupported kind: {kind}"
                )
            if column not in fields:
                raise ContractError(
                    f"distribution[{index}] references unknown field: {column}"
                )


def load_contract(path: str | Path) -> DataContract:
    """Load a JSON contract from disk."""

    contract_path = Path(path)
    try:
        payload = json.loads(contract_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ContractError(f"Invalid JSON in {contract_path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ContractError("Contract root must be an object")
    return DataContract.from_dict(payload)
