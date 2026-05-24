import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

import server
from tests.fixtures import SAMPLE_CSV, SAMPLE_CSV_WITHOUT_IDS, read_csv_text


class ServerToolTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.data_path = Path(self.tmpdir.name) / "pfm-gio.csv"
        self.original_data_path = server.DATA_PATH
        server.DATA_PATH = str(self.data_path)
        self.data_path.write_text(SAMPLE_CSV, encoding="utf-8")

    def tearDown(self):
        server.DATA_PATH = self.original_data_path
        self.tmpdir.cleanup()

    def test_load_data_cleans_and_generates_missing_transaction_ids(self):
        self.data_path.write_text(SAMPLE_CSV_WITHOUT_IDS, encoding="utf-8")

        df = server.load_data()

        self.assertEqual(len(df), 2)
        self.assertIn(server.ID_COLUMN, df.columns)
        self.assertTrue(df[server.ID_COLUMN].str.len().gt(0).all())
        self.assertEqual(df["Amount"].tolist(), [5000, 1200])
        self.assertIn(server.ID_COLUMN, read_csv_text(self.data_path))

    def test_calculate_totals_filters_by_year_month_and_category(self):
        totals = server.calculate_totals(year=2025, month=1)

        self.assertEqual(totals["income"], 5000)
        self.assertEqual(totals["expenses"], 1350)
        self.assertEqual(totals["balance"], 3650)
        self.assertEqual(totals["transaction_count"], 3)

        restaurant = server.calculate_totals(year=2025, category="rest")
        self.assertEqual(restaurant["expenses"], 150)
        self.assertEqual(restaurant["transaction_count"], 1)

    def test_list_transactions_filters_and_orders_results(self):
        payload = server.list_transactions(year=2025, category="salary", limit=10)
        rows = json.loads(payload)

        self.assertEqual([row["transaction_id"] for row in rows], ["tx-income-feb", "tx-income-jan"])
        self.assertEqual(rows[0]["Date"], "2025-02-10T00:00:00.000")

    def test_expense_grouping_tools(self):
        by_category = server.expenses_by_category(year=2025)
        self.assertEqual(
            {row["category"]: row["total"] for row in by_category},
            {"home": 1200, "vacaciones": 800, "restaurant": 150},
        )

        by_month = server.expenses_by_month_for_category("vacaciones", year=2025)
        self.assertEqual(by_month, [{"month": 2, "total": 800}])

    def test_add_update_and_delete_transaction_persist_to_csv(self):
        added = server.add_transaction(
            description="coffee",
            transaction_type="expensive",
            amount=12.5,
            category="restaurant",
            date="2025-03-01",
        )

        new_id = added["transaction"][server.ID_COLUMN]
        self.assertEqual(added["transaction_count"], 7)
        self.assertEqual(added["transaction"]["Date"], "2025-03-01")

        updated = server.update_transaction(
            transaction_id=new_id,
            amount=15,
            category="food",
        )
        self.assertEqual(updated["transaction"]["Amount"], 15)
        self.assertEqual(updated["transaction"]["Category"], "food")

        deleted = server.delete_transaction(new_id)
        self.assertEqual(deleted["deleted_transaction"][server.ID_COLUMN], new_id)
        self.assertEqual(deleted["transaction_count"], 6)

        persisted = pd.read_csv(self.data_path, sep=";")
        self.assertNotIn(new_id, persisted[server.ID_COLUMN].astype(str).tolist())

    def test_batch_add_validation_and_limit(self):
        result = server.add_transactions_batch(
            [
                {
                    "description": "bus",
                    "transaction_type": "expensive",
                    "amount": 3,
                    "category": "vehicle",
                    "date": "2025-03-01",
                },
                {
                    "description": "gift",
                    "transaction_type": "expensive",
                    "amount": 20,
                    "category": "gift",
                    "date": "2025-03-02",
                },
            ]
        )

        self.assertEqual(result["added_count"], 2)
        self.assertEqual(result["transaction_count"], 8)

        with self.assertRaisesRegex(ValueError, "Maximum"):
            server.add_transactions_batch(
                [
                    {
                        "description": f"tx-{i}",
                        "transaction_type": "expensive",
                        "amount": 1,
                        "category": "other",
                    }
                    for i in range(server.MAX_BATCH_TRANSACTIONS + 1)
                ]
            )

    def test_update_and_delete_require_existing_transaction(self):
        with self.assertRaisesRegex(ValueError, "Transaction not found"):
            server.update_transaction("missing-id", amount=1)

        with self.assertRaisesRegex(ValueError, "Transaction not found"):
            server.delete_transaction("missing-id")


if __name__ == "__main__":
    unittest.main()
