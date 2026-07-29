import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

from data_observer.contract import load_contract
from data_observer.engine import evaluate
from data_observer.reporting import incident_summary, render_markdown


ROOT = Path(__file__).resolve().parents[1]


class ReportingTests(unittest.TestCase):
    def test_markdown_is_explicitly_synthetic_and_actionable(self) -> None:
        report = evaluate(
            load_contract(ROOT / "contracts/orders.contract.json"),
            ROOT / "data/orders_incident.csv",
            now=datetime(2026, 7, 28, 12, 0, tzinfo=timezone.utc),
        )
        markdown = render_markdown(report)
        self.assertIn("Synthetic portfolio demo", markdown)
        self.assertIn("Recommended response", markdown)
        self.assertIn("Quarantine the batch", markdown)
        self.assertIn("point-in-time", markdown)

    def test_checked_in_examples_match_generated_incidents(self) -> None:
        contract = load_contract(ROOT / "contracts/orders.contract.json")
        now = datetime(2026, 7, 28, 12, 0, tzinfo=timezone.utc)
        fixtures = {
            "orders_healthy.csv": "healthy-incident.json",
            "orders_incident.csv": "breached-incident.json",
        }
        for data_name, example_name in fixtures.items():
            with self.subTest(example=example_name):
                report = evaluate(contract, ROOT / f"data/{data_name}", now=now)
                expected = json.loads(
                    (ROOT / f"docs/examples/{example_name}").read_text(
                        encoding="utf-8"
                    )
                )
                self.assertEqual(incident_summary(report), expected)


if __name__ == "__main__":
    unittest.main()
