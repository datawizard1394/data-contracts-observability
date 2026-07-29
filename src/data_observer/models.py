"""Core result models for observability evaluations."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


class CheckStatus(str, Enum):
    """Normalized outcome for a data-quality check."""

    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


@dataclass(frozen=True)
class CheckResult:
    """A single deterministic data-quality observation."""

    check_id: str
    dimension: str
    status: CheckStatus
    severity: str
    observed: Any
    expected: str
    message: str
    failing_rows: tuple[int, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["status"] = self.status.value
        payload["failing_rows"] = list(self.failing_rows)
        return payload


@dataclass(frozen=True)
class ValidationReport:
    """Aggregate output for one contract evaluation."""

    dataset: str
    contract_version: str
    source_file: str
    row_count: int
    results: tuple[CheckResult, ...]
    slo_target_percent: float
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    lineage: dict[str, Any] | None = None

    @property
    def counts(self) -> dict[str, int]:
        return {
            status.value: sum(result.status is status for result in self.results)
            for status in CheckStatus
        }

    @property
    def evaluation_score_percent(self) -> float:
        """Return a transparent point-in-time compliance score.

        A pass is worth one point, a warning half a point, and a failure zero.
        This is deliberately not represented as a historical availability SLI.
        """

        if not self.results:
            return 100.0
        points = sum(
            1.0
            if result.status is CheckStatus.PASS
            else 0.5
            if result.status is CheckStatus.WARN
            else 0.0
            for result in self.results
        )
        return round(points / len(self.results) * 100, 2)

    @property
    def is_healthy(self) -> bool:
        return (
            self.counts[CheckStatus.FAIL.value] == 0
            and self.evaluation_score_percent >= self.slo_target_percent
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset": self.dataset,
            "contract_version": self.contract_version,
            "source_file": self.source_file,
            "row_count": self.row_count,
            "generated_at": self.generated_at,
            "status": "HEALTHY" if self.is_healthy else "BREACHED",
            "counts": self.counts,
            "evaluation_score_percent": self.evaluation_score_percent,
            "slo_target_percent": self.slo_target_percent,
            "checks": [result.to_dict() for result in self.results],
            "lineage": self.lineage,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ValidationReport":
        results = tuple(
            CheckResult(
                check_id=item["check_id"],
                dimension=item["dimension"],
                status=CheckStatus(item["status"]),
                severity=item["severity"],
                observed=item.get("observed"),
                expected=item["expected"],
                message=item["message"],
                failing_rows=tuple(item.get("failing_rows", ())),
                metadata=item.get("metadata", {}),
            )
            for item in payload["checks"]
        )
        return cls(
            dataset=payload["dataset"],
            contract_version=payload["contract_version"],
            source_file=payload["source_file"],
            row_count=int(payload["row_count"]),
            results=results,
            slo_target_percent=float(payload["slo_target_percent"]),
            generated_at=payload["generated_at"],
            lineage=payload.get("lineage"),
        )

    @property
    def source_name(self) -> str:
        return Path(self.source_file).name
