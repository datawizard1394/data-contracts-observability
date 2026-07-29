import unittest
from pathlib import Path

from data_observer.lineage import (
    LineageError,
    lineage_context,
    load_lineage,
    validate_manifest,
)


ROOT = Path(__file__).resolve().parents[1]


class LineageTests(unittest.TestCase):
    def test_returns_direct_and_transitive_impact(self) -> None:
        manifest = load_lineage(ROOT / "lineage/manifest.json")
        context = lineage_context(manifest, "silver.orders_clean")
        self.assertEqual(context["direct_upstream"], ["bronze.orders_ingest"])
        self.assertEqual(context["direct_downstream"], ["gold.order_metrics"])
        self.assertEqual(
            context["transitive_downstream"],
            ["dashboard.order_operations", "gold.order_metrics"],
        )
        self.assertIn("source.commerce.orders", context["transitive_upstream"])

    def test_rejects_cycles(self) -> None:
        manifest = {
            "assets": [
                {"name": "a", "upstream": ["b"]},
                {"name": "b", "upstream": ["a"]},
            ]
        }
        with self.assertRaisesRegex(LineageError, "Cycle"):
            validate_manifest(manifest)

    def test_rejects_unknown_asset_lookup(self) -> None:
        manifest = load_lineage(ROOT / "lineage/manifest.json")
        with self.assertRaisesRegex(LineageError, "not found"):
            lineage_context(manifest, "missing.asset")


if __name__ == "__main__":
    unittest.main()
