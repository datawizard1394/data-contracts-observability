"""Evaluation orchestration for data contracts."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .checks import (
    distribution_checks,
    freshness_check,
    schema_checks,
    uniqueness_checks,
    volume_check,
)
from .contract import DataContract
from .io import read_csv
from .models import ValidationReport


def evaluate(
    contract: DataContract,
    data_path: str | Path,
    *,
    now: datetime | None = None,
    lineage: dict | None = None,
) -> ValidationReport:
    """Execute all configured checks and return a normalized report."""

    evaluation_time = now or datetime.now(timezone.utc)
    if evaluation_time.tzinfo is None:
        evaluation_time = evaluation_time.replace(tzinfo=timezone.utc)
    rows, headers = read_csv(data_path)
    results = schema_checks(contract, rows, headers)

    volume = volume_check(contract, len(rows))
    if volume is not None:
        results.append(volume)
    freshness = freshness_check(contract, rows, evaluation_time)
    if freshness is not None:
        results.append(freshness)
    results.extend(uniqueness_checks(contract, rows))
    results.extend(distribution_checks(contract, rows))

    return ValidationReport(
        dataset=contract.dataset,
        contract_version=contract.version,
        source_file=str(Path(data_path)),
        row_count=len(rows),
        results=tuple(results),
        slo_target_percent=contract.slo_target_percent,
        generated_at=evaluation_time.astimezone(timezone.utc).isoformat(),
        lineage=lineage,
    )
