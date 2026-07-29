import unittest
from datetime import datetime, timezone
from pathlib import Path

from data_observer.contract import load_contract
from data_observer.engine import evaluate
from data_observer.models import CheckStatus
from data_observer.reporting import incident_summary


ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 7, 28, 12, 0, tzinfo=timezone.utc)


class EngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = load_contract(ROOT / "contracts/orders.contract.json")

    def test_healthy_dataset_passes_every_check(self) -> None:
        report = evaluate(
            self.contract,
            ROOT / "data/orders_healthy.csv",
            now=NOW,
        )
        self.assertTrue(report.is_healthy)
        self.assertEqual(report.row_count, 8)
        self.assertEqual(report.counts["FAIL"], 0)
        self.assertEqual(report.counts["WARN"], 0)
        self.assertEqual(report.evaluation_score_percent, 100.0)

    def test_incident_dataset_surfaces_multiple_dimensions(self) -> None:
        report = evaluate(
            self.contract,
            ROOT / "data/orders_incident.csv",
            now=NOW,
        )
        failures = {
            result.check_id
            for result in report.results
            if result.status is CheckStatus.FAIL
        }
        self.assertFalse(report.is_healthy)
        self.assertIn("volume.row_count", failures)
        self.assertIn("freshness.latest_record", failures)
        self.assertIn("uniqueness.order_id", failures)
        self.assertIn("distribution.status.domain", failures)
        self.assertIn("distribution.amount_usd.range", failures)
        self.assertEqual(incident_summary(report)["severity"], "SEV-1")

    def test_nullability_reports_csv_line_number(self) -> None:
        report = evaluate(
            self.contract,
            ROOT / "data/orders_incident.csv",
            now=NOW,
        )
        result = next(
            item
            for item in report.results
            if item.check_id == "schema.customer_id.nullability"
        )
        self.assertEqual(result.failing_rows, (4,))


if __name__ == "__main__":
    unittest.main()
