"""Incident and SLO-oriented presentation helpers."""

from __future__ import annotations

from .models import CheckStatus, ValidationReport


RUNBOOK_ACTIONS = {
    "schema": "Quarantine the batch and compare producer schema with the contract.",
    "freshness": "Check the ingestion schedule, source availability, and last good run.",
    "volume": "Compare source counts and inspect upstream filters or partial extracts.",
    "uniqueness": "Identify replayed keys and verify merge/idempotency logic.",
    "distribution": "Profile affected rows and confirm whether the shift is expected.",
}


def incident_summary(report: ValidationReport) -> dict:
    """Build a machine-readable incident/SLO summary."""

    actionable = [
        result
        for result in report.results
        if result.status in (CheckStatus.FAIL, CheckStatus.WARN)
    ]
    critical_failures = [
        result
        for result in actionable
        if result.status is CheckStatus.FAIL and result.severity == "critical"
    ]
    if not actionable and report.is_healthy:
        severity = "NONE"
    elif report.dataset and critical_failures:
        severity = "SEV-1" if len(critical_failures) >= 2 else "SEV-2"
    else:
        severity = "SEV-3"
    dimensions = sorted({result.dimension for result in actionable})
    return {
        "state": "HEALTHY" if report.is_healthy else "BREACHED",
        "severity": severity,
        "dataset": report.dataset,
        "generated_at": report.generated_at,
        "evaluation_score_percent": report.evaluation_score_percent,
        "slo_target_percent": report.slo_target_percent,
        "failed_checks": [
            result.check_id
            for result in actionable
            if result.status is CheckStatus.FAIL
        ],
        "warning_checks": [
            result.check_id
            for result in actionable
            if result.status is CheckStatus.WARN
        ],
        "affected_dimensions": dimensions,
        "recommended_actions": [RUNBOOK_ACTIONS[item] for item in dimensions],
        "synthetic_demo": True,
        "slo_note": (
            "The score is a point-in-time contract evaluation, not historical "
            "production availability."
        ),
    }


def render_markdown(report: ValidationReport) -> str:
    incident = incident_summary(report)
    lines = [
        "# Data Contract Evaluation",
        "",
        "> **Synthetic portfolio demo:** all data and incident outcomes are illustrative.",
        "",
        f"- **Dataset:** `{report.dataset}`",
        f"- **State:** `{incident['state']}`",
        f"- **Incident severity:** `{incident['severity']}`",
        (
            f"- **Evaluation score:** `{report.evaluation_score_percent:.2f}%` "
            f"(target `{report.slo_target_percent:.2f}%`)"
        ),
        f"- **Rows observed:** `{report.row_count}`",
        f"- **Evaluated at:** `{report.generated_at}`",
        "",
        "## Check results",
        "",
        "| Check | Dimension | Status | Observed | Expected |",
        "|---|---|---:|---|---|",
    ]
    for result in report.results:
        observed = str(result.observed).replace("|", "\\|")
        expected = result.expected.replace("|", "\\|")
        lines.append(
            f"| `{result.check_id}` | {result.dimension} | **{result.status.value}** "
            f"| {observed} | {expected} |"
        )

    lines.extend(["", "## Recommended response", ""])
    if incident["recommended_actions"]:
        lines.extend(
            f"{index}. {action}"
            for index, action in enumerate(incident["recommended_actions"], start=1)
        )
    else:
        lines.append("No incident response required. Continue scheduled monitoring.")
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            incident["slo_note"],
            "",
        ]
    )
    return "\n".join(lines)


def console_summary(report: ValidationReport) -> str:
    counts = report.counts
    return (
        f"{report.dataset}: {'HEALTHY' if report.is_healthy else 'BREACHED'} | "
        f"score={report.evaluation_score_percent:.2f}% | "
        f"pass={counts['PASS']} warn={counts['WARN']} fail={counts['FAIL']}"
    )
