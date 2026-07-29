"""Dependency-free schema and observability checks."""

from __future__ import annotations

import math
from collections import Counter
from datetime import date, datetime, timezone
from typing import Any, Iterable

from .contract import DataContract, FieldSpec
from .models import CheckResult, CheckStatus


def _failure_status(severity: str) -> CheckStatus:
    return CheckStatus.WARN if severity.lower() == "warning" else CheckStatus.FAIL


def _parse_datetime(value: str) -> datetime:
    normalized = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _is_type(value: str, data_type: str) -> bool:
    try:
        if data_type == "string":
            return isinstance(value, str)
        if data_type == "integer":
            int(value)
            return "." not in value
        if data_type == "number":
            return math.isfinite(float(value))
        if data_type == "boolean":
            return value.strip().lower() in {"true", "false", "1", "0", "yes", "no"}
        if data_type == "date":
            date.fromisoformat(value)
            return True
        if data_type == "datetime":
            _parse_datetime(value)
            return True
    except (TypeError, ValueError, OverflowError):
        return False
    return False


def schema_checks(
    contract: DataContract,
    rows: list[dict[str, str | None]],
    headers: Iterable[str],
) -> list[CheckResult]:
    """Validate required columns, nullability, and primitive field types."""

    results: list[CheckResult] = []
    header_set = set(headers)
    missing = [name for name in contract.field_names if name not in header_set]
    unexpected = sorted(header_set - set(contract.field_names))
    results.append(
        CheckResult(
            check_id="schema.columns",
            dimension="schema",
            status=CheckStatus.FAIL if missing else CheckStatus.PASS,
            severity="critical",
            observed={"missing": missing, "unexpected": unexpected},
            expected="all contract fields present",
            message=(
                f"Missing contract columns: {', '.join(missing)}"
                if missing
                else "All contract columns are present"
            ),
            metadata={"unexpected_columns_are_allowed": True},
        )
    )
    for field_spec in contract.fields:
        if field_spec.name in missing:
            continue
        results.extend(_field_schema_checks(field_spec, rows))
    return results


def _field_schema_checks(
    field_spec: FieldSpec, rows: list[dict[str, str | None]]
) -> list[CheckResult]:
    null_rows = tuple(
        index
        for index, row in enumerate(rows, start=2)
        if row.get(field_spec.name) is None
    )
    null_failure = bool(null_rows and not field_spec.nullable)
    null_result = CheckResult(
        check_id=f"schema.{field_spec.name}.nullability",
        dimension="schema",
        status=CheckStatus.FAIL if null_failure else CheckStatus.PASS,
        severity="critical",
        observed=len(null_rows),
        expected="0 nulls" if not field_spec.nullable else "nulls permitted",
        message=(
            f"{field_spec.name} has {len(null_rows)} disallowed null value(s)"
            if null_failure
            else f"{field_spec.name} satisfies nullability"
        ),
        failing_rows=null_rows if null_failure else (),
    )

    invalid_rows = tuple(
        index
        for index, row in enumerate(rows, start=2)
        if row.get(field_spec.name) is not None
        and not _is_type(str(row[field_spec.name]), field_spec.data_type)
    )
    type_result = CheckResult(
        check_id=f"schema.{field_spec.name}.type",
        dimension="schema",
        status=CheckStatus.FAIL if invalid_rows else CheckStatus.PASS,
        severity="critical",
        observed=len(invalid_rows),
        expected=field_spec.data_type,
        message=(
            f"{field_spec.name} has {len(invalid_rows)} invalid {field_spec.data_type} "
            "value(s)"
            if invalid_rows
            else f"{field_spec.name} values match {field_spec.data_type}"
        ),
        failing_rows=invalid_rows,
    )
    return [null_result, type_result]


def volume_check(contract: DataContract, row_count: int) -> CheckResult | None:
    config = contract.checks.get("volume")
    if not config:
        return None
    minimum = int(config.get("min_rows", 0))
    maximum = int(config.get("max_rows", 2**63 - 1))
    severity = str(config.get("severity", "critical"))
    failed = row_count < minimum or row_count > maximum
    return CheckResult(
        check_id="volume.row_count",
        dimension="volume",
        status=_failure_status(severity) if failed else CheckStatus.PASS,
        severity=severity,
        observed=row_count,
        expected=f"{minimum} <= rows <= {maximum}",
        message=(
            f"Row count {row_count} is outside [{minimum}, {maximum}]"
            if failed
            else f"Row count {row_count} is within the expected range"
        ),
    )


def freshness_check(
    contract: DataContract,
    rows: list[dict[str, str | None]],
    now: datetime,
) -> CheckResult | None:
    config = contract.checks.get("freshness")
    if not config:
        return None
    column = str(config["timestamp_column"])
    limit_minutes = float(config["max_age_minutes"])
    future_skew = float(config.get("max_future_skew_minutes", 5))
    severity = str(config.get("severity", "critical"))
    parsed: list[datetime] = []
    invalid_rows: list[int] = []
    for index, row in enumerate(rows, start=2):
        value = row.get(column)
        if value is None:
            continue
        try:
            parsed.append(_parse_datetime(str(value)))
        except ValueError:
            invalid_rows.append(index)

    if not parsed:
        return CheckResult(
            check_id="freshness.latest_record",
            dimension="freshness",
            status=_failure_status(severity),
            severity=severity,
            observed=None,
            expected=f"latest {column} no older than {limit_minutes:g} minutes",
            message=f"No valid timestamps found in {column}",
            failing_rows=tuple(invalid_rows),
        )

    now_utc = now.astimezone(timezone.utc)
    latest = max(parsed)
    age_minutes = (now_utc - latest).total_seconds() / 60
    failed = age_minutes > limit_minutes or age_minutes < -future_skew
    reason = (
        f"latest record is {age_minutes:.1f} minutes old"
        if age_minutes >= 0
        else f"latest record is {-age_minutes:.1f} minutes in the future"
    )
    return CheckResult(
        check_id="freshness.latest_record",
        dimension="freshness",
        status=_failure_status(severity) if failed else CheckStatus.PASS,
        severity=severity,
        observed={
            "latest_timestamp": latest.isoformat(),
            "age_minutes": round(age_minutes, 2),
            "invalid_timestamp_rows": invalid_rows,
        },
        expected=(
            f"-{future_skew:g} <= age_minutes <= {limit_minutes:g}"
        ),
        message=f"Freshness {'breached' if failed else 'satisfied'}: {reason}",
        failing_rows=tuple(invalid_rows),
    )


def uniqueness_checks(
    contract: DataContract, rows: list[dict[str, str | None]]
) -> list[CheckResult]:
    results: list[CheckResult] = []
    for column in contract.checks.get("uniqueness", []):
        values = [row.get(column) for row in rows if row.get(column) is not None]
        counts = Counter(values)
        duplicates = {value for value, count in counts.items() if count > 1}
        failing_rows = tuple(
            index
            for index, row in enumerate(rows, start=2)
            if row.get(column) in duplicates
        )
        results.append(
            CheckResult(
                check_id=f"uniqueness.{column}",
                dimension="uniqueness",
                status=CheckStatus.FAIL if duplicates else CheckStatus.PASS,
                severity="critical",
                observed={
                    "duplicate_values": len(duplicates),
                    "affected_rows": len(failing_rows),
                },
                expected="no duplicate non-null values",
                message=(
                    f"{column} has {len(duplicates)} duplicate value(s)"
                    if duplicates
                    else f"{column} is unique"
                ),
                failing_rows=failing_rows,
            )
        )
    return results


def distribution_checks(
    contract: DataContract, rows: list[dict[str, str | None]]
) -> list[CheckResult]:
    results: list[CheckResult] = []
    for index, config in enumerate(contract.checks.get("distribution", []), start=1):
        kind = str(config["kind"])
        column = str(config["column"])
        severity = str(config.get("severity", "warning"))
        check_id = str(config.get("id", f"distribution.{column}.{kind}.{index}"))
        if kind == "allowed_values":
            result = _allowed_values(check_id, column, config, rows, severity)
        elif kind == "range":
            result = _numeric_range(check_id, column, config, rows, severity)
        else:
            result = _null_rate(check_id, column, config, rows, severity)
        results.append(result)
    return results


def _allowed_values(
    check_id: str,
    column: str,
    config: dict[str, Any],
    rows: list[dict[str, str | None]],
    severity: str,
) -> CheckResult:
    allowed = {str(item) for item in config["values"]}
    populated = [
        (index, str(row[column]))
        for index, row in enumerate(rows, start=2)
        if row.get(column) is not None
    ]
    failing_rows = tuple(index for index, value in populated if value not in allowed)
    rate = len(failing_rows) / len(populated) if populated else 0.0
    limit = float(config.get("max_violation_rate", 0))
    failed = rate > limit
    return CheckResult(
        check_id=check_id,
        dimension="distribution",
        status=_failure_status(severity) if failed else CheckStatus.PASS,
        severity=severity,
        observed={"violation_rate": round(rate, 4), "violations": len(failing_rows)},
        expected=f"violation_rate <= {limit}; values in {sorted(allowed)}",
        message=f"{column} allowed-value violation rate is {rate:.2%}",
        failing_rows=failing_rows,
    )


def _numeric_range(
    check_id: str,
    column: str,
    config: dict[str, Any],
    rows: list[dict[str, str | None]],
    severity: str,
) -> CheckResult:
    minimum = float(config["min"])
    maximum = float(config["max"])
    populated = [
        (index, row[column])
        for index, row in enumerate(rows, start=2)
        if row.get(column) is not None
    ]
    failing: list[int] = []
    for index, value in populated:
        try:
            number = float(str(value))
        except (TypeError, ValueError):
            failing.append(index)
            continue
        if not math.isfinite(number) or not minimum <= number <= maximum:
            failing.append(index)
    rate = len(failing) / len(populated) if populated else 0.0
    limit = float(config.get("max_violation_rate", 0))
    failed = rate > limit
    return CheckResult(
        check_id=check_id,
        dimension="distribution",
        status=_failure_status(severity) if failed else CheckStatus.PASS,
        severity=severity,
        observed={"violation_rate": round(rate, 4), "violations": len(failing)},
        expected=(
            f"{minimum:g} <= {column} <= {maximum:g}; "
            f"violation_rate <= {limit}"
        ),
        message=f"{column} range violation rate is {rate:.2%}",
        failing_rows=tuple(failing),
    )


def _null_rate(
    check_id: str,
    column: str,
    config: dict[str, Any],
    rows: list[dict[str, str | None]],
    severity: str,
) -> CheckResult:
    null_rows = tuple(
        index
        for index, row in enumerate(rows, start=2)
        if row.get(column) is None
    )
    rate = len(null_rows) / len(rows) if rows else 0.0
    limit = float(config["max_rate"])
    failed = rate > limit
    return CheckResult(
        check_id=check_id,
        dimension="distribution",
        status=_failure_status(severity) if failed else CheckStatus.PASS,
        severity=severity,
        observed={"null_rate": round(rate, 4), "nulls": len(null_rows)},
        expected=f"null_rate <= {limit}",
        message=f"{column} null rate is {rate:.2%}",
        failing_rows=null_rows,
    )
