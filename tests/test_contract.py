import json
import unittest
from pathlib import Path

from data_observer.contract import ContractError, DataContract, load_contract


ROOT = Path(__file__).resolve().parents[1]


class ContractTests(unittest.TestCase):
    def test_loads_reference_contract(self) -> None:
        contract = load_contract(ROOT / "contracts/orders.contract.json")
        self.assertEqual(contract.dataset, "silver.orders_clean")
        self.assertEqual(contract.version, "1.2.0")
        self.assertEqual(len(contract.fields), 6)
        self.assertTrue(contract.synthetic)

    def test_rejects_unknown_check_column(self) -> None:
        payload = json.loads(
            (ROOT / "contracts/orders.contract.json").read_text(encoding="utf-8")
        )
        payload["checks"]["freshness"]["timestamp_column"] = "missing_timestamp"
        with self.assertRaisesRegex(ContractError, "unknown field"):
            DataContract.from_dict(payload)

    def test_rejects_duplicate_schema_fields(self) -> None:
        payload = {
            "dataset": "demo.asset",
            "version": "1",
            "owner": "owner@example.invalid",
            "schema": [
                {"name": "id", "type": "string"},
                {"name": "id", "type": "integer"},
            ],
        }
        with self.assertRaisesRegex(ContractError, "Duplicate"):
            DataContract.from_dict(payload)


if __name__ == "__main__":
    unittest.main()
