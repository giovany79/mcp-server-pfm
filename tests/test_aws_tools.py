import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AWS_SRC = ROOT / "aws-deploy" / "src"
sys.path.insert(0, str(AWS_SRC))

from tools import FinanceTools  # noqa: E402
from tests.fixtures import FakeS3, SAMPLE_CSV, SAMPLE_CSV_WITHOUT_IDS


def make_tools(csv_text=SAMPLE_CSV):
    tools = FinanceTools.__new__(FinanceTools)
    tools.bucket_name = "test-bucket"
    tools.file_key = "pfm-gio.csv"
    tools._df = None
    tools.s3 = FakeS3(csv_text)
    tools.id_column = "transaction_id"
    tools.base_columns = [tools.id_column, "Description", "Income/expensive", "Amount", "Category", "Date"]
    tools.max_batch_transactions = 20
    return tools


class AwsFinanceToolsTests(unittest.TestCase):
    def test_load_data_reads_from_s3_and_persists_generated_ids(self):
        tools = make_tools(SAMPLE_CSV_WITHOUT_IDS)

        df = tools.load_data()

        self.assertEqual(len(df), 2)
        self.assertIn("transaction_id", df.columns)
        self.assertEqual(len(tools.s3.put_calls), 1)
        self.assertIn("transaction_id", tools.s3.csv_text)

    def test_calculate_and_list_transactions(self):
        tools = make_tools()

        totals = tools.calculate_totals(year=2025, month=1)
        self.assertEqual(totals["income"], 5000)
        self.assertEqual(totals["expenses"], 1350)
        self.assertEqual(totals["balance"], 3650)

        rows = tools.list_transactions(category="all", year=2025, limit=0)
        self.assertEqual(len(rows), 5)
        self.assertEqual(rows[0]["Date"], "2025-02-10")

    def test_mutation_tools_persist_to_fake_s3(self):
        tools = make_tools()

        added = tools.add_transaction("coffee", "expensive", 12, "restaurant", "2025-03-01")
        new_id = added["transaction"]["transaction_id"]
        self.assertEqual(added["transaction_count"], 7)
        self.assertEqual(len(tools.s3.put_calls), 1)

        updated = tools.update_transaction(new_id, category="food", amount=14)
        self.assertEqual(updated["transaction"]["Category"], "food")
        self.assertEqual(updated["transaction"]["Amount"], 14)

        deleted = tools.delete_transaction(new_id)
        self.assertEqual(deleted["deleted_transaction"]["transaction_id"], new_id)
        self.assertEqual(deleted["transaction_count"], 6)
        self.assertEqual(len(tools.s3.put_calls), 3)

    def test_mutations_require_bucket_name(self):
        tools = make_tools()
        tools.bucket_name = None

        with self.assertRaisesRegex(RuntimeError, "DATA_BUCKET"):
            tools.add_transaction("coffee", "expensive", 12, "restaurant")

        with self.assertRaisesRegex(RuntimeError, "DATA_BUCKET"):
            tools.add_transactions_batch(
                [
                    {
                        "description": "coffee",
                        "transaction_type": "expensive",
                        "amount": 12,
                        "category": "restaurant",
                    }
                ]
            )


if __name__ == "__main__":
    unittest.main()
