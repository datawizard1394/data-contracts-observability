# Data Contract Incident Runbook

> **Scope:** This runbook belongs to a synthetic portfolio demonstration.
> Dataset names, contacts, incidents, timestamps, and service levels are
> illustrative; they do not represent a live production environment.

## Purpose

Use this procedure when `data-observer` reports `BREACHED`, a CI quality gate
returns a non-zero status, or a scheduled contract evaluation produces one or
more failed checks.

The goal is to contain bad data first, identify the failing layer, communicate
impact through lineage, and restore from the last known-good point without
silently weakening the contract.

## Detection contract

| Signal | Default response | Owner |
|---|---|---|
| Schema or type failure | Stop publication; quarantine batch | Data platform |
| Freshness breach | Confirm upstream availability and scheduler state | Data platform |
| Volume outside bounds | Compare source and landing counts | Pipeline owner |
| Duplicate business key | Stop non-idempotent downstream writes | Pipeline owner |
| Critical distribution failure | Quarantine affected partitions | Domain owner |
| Warning-only distribution shift | Investigate while publication continues | Domain owner |

## First 15 minutes

1. Record the dataset, contract version, evaluation timestamp, and source file.
2. Open `incident.json`; use `failed_checks` and `affected_dimensions` as the
   initial scope. Do not infer impact from row count alone.
3. Open `lineage-context.json`; notify the owners of direct downstream assets.
4. Prevent the failing batch from replacing the last known-good partition.
5. Preserve the source extract, generated report, and orchestration logs for
   reproducibility.
6. Assign severity:
   - **SEV-1:** multiple critical dimensions fail or trusted downstream
     reporting is already affected.
   - **SEV-2:** one critical check fails before downstream publication.
   - **SEV-3:** warning-only degradation or a non-critical SLO miss.

## Diagnosis by dimension

### Schema

- Compare the producer payload with `contracts/orders.contract.json`.
- Distinguish an intentional additive field from a breaking removal, rename,
  nullability change, or type change.
- Additive fields are reported but allowed by this demo; breaking changes fail.
- If the change is intentional, update the contract version and tests through
  review. Never patch the runtime to ignore an undocumented breaking change.

### Freshness

- Verify the most recent valid event timestamp, not only file modification time.
- Check source health, credentials, orchestration dependencies, and retries.
- Inspect clock skew if timestamps are in the future.
- Backfill only after confirming an idempotent write path.

### Volume

- Compare counts at source, landing, transformation, and publication layers.
- Check unexpected filters, partition predicates, pagination, and partial files.
- Treat a plausible-looking partial batch as a failure until completeness is
  established.

### Uniqueness

- Group affected business keys and locate the earliest duplicated stage.
- Determine whether the cause is source replay, retry behavior, or merge logic.
- Prefer a deterministic idempotency key over row-order-based deduplication.

### Distribution

- Profile only the affected columns and partitions first.
- Validate the contract boundary with the domain owner before widening it.
- Separate genuine business shifts from malformed values and unit/currency
  changes.

## Containment and recovery

1. Mark the affected batch as quarantined.
2. Keep the last known-good downstream asset available when safe.
3. Correct the producer, transformation, or contract through reviewed change.
4. Re-run the exact failing fixture and timestamp to prove reproducibility.
5. Run `make check`, `make demo`, and a targeted incident replay.
6. Republish in dependency order and confirm direct downstream consumers.
7. Close only when critical checks pass and the point-in-time score meets the
   configured target.

## Communication template

```text
[SYNTHETIC EXAMPLE] Data contract incident: <dataset>
Severity: <SEV-1|SEV-2|SEV-3>
Detected: <UTC timestamp>
Impact: <affected assets from lineage>
Failed checks: <check ids>
Containment: <quarantine / last-known-good state>
Next update: <time and owner>
```

## SLO interpretation

The demo calculates a **point-in-time contract evaluation score**:

- pass = 1 point
- warning = 0.5 points
- failure = 0 points

That score is useful for one evaluation but is not a historical availability
SLI. A production implementation should persist evaluation events and calculate
windowed reliability, error budget, burn rate, and time-to-detect separately.

## Post-incident review

Capture the trigger, impact path, containment time, root cause, contributing
factors, corrective actions, owners, and due dates. Add a regression fixture
that would have detected the issue before changing the contract or closing the
review.
