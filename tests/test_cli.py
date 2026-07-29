import json
import tempfile
import unittest
from pathlib import Path

from data_observer.cli import main


ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def test_run_writes_verified_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            exit_code = main(
                [
                    "run",
                    "--contract",
                    str(ROOT / "contracts/orders.contract.json"),
                    "--data",
                    str(ROOT / "data/orders_healthy.csv"),
                    "--lineage",
                    str(ROOT / "lineage/manifest.json"),
                    "--output-dir",
                    str(output),
                    "--now",
                    "2026-07-28T12:00:00Z",
                ]
            )
            self.assertEqual(exit_code, 0)
            report = json.loads(
                (output / "report.json").read_text(encoding="utf-8")
            )
            self.assertEqual(report["status"], "HEALTHY")
            self.assertEqual(report["lineage"]["direct_downstream"], ["gold.order_metrics"])
            self.assertTrue((output / "incident.json").exists())
            self.assertTrue((output / "incident-summary.md").exists())
            self.assertTrue((output / "lineage-context.json").exists())

    def test_failed_checks_return_nonzero_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            exit_code = main(
                [
                    "run",
                    "--contract",
                    str(ROOT / "contracts/orders.contract.json"),
                    "--data",
                    str(ROOT / "data/orders_incident.csv"),
                    "--output-dir",
                    temporary,
                    "--now",
                    "2026-07-28T12:00:00Z",
                ]
            )
            self.assertEqual(exit_code, 1)

    def test_fail_on_never_supports_diagnostic_runs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            exit_code = main(
                [
                    "run",
                    "--contract",
                    str(ROOT / "contracts/orders.contract.json"),
                    "--data",
                    str(ROOT / "data/orders_incident.csv"),
                    "--output-dir",
                    temporary,
                    "--now",
                    "2026-07-28T12:00:00Z",
                    "--fail-on",
                    "never",
                ]
            )
            self.assertEqual(exit_code, 0)


if __name__ == "__main__":
    unittest.main()
