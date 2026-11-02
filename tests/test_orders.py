
import unittest
from unittest.mock import patch

from src.tools.orders import (
    get_order_status,
    get_order_items,
)


class TestOrders(unittest.TestCase):

    def setUp(self):
        self.data = {
            "customers.csv": [
                {
                    "customer_id": "1",
                    "name": "Test Customer",
                    "email": "customer@example.com"
                }
            ],
            "orders.csv": [
                {
                    "order_id": "10",
                    "customer_id": "1",
                    "order_date": "2025-10-01",
                    "status": "shipped",
                    "total_brl": "999.90",
                    "payment_method": "pix",
                    "tracking_code": "BR123456789BR",
                    "estimated_delivery": "2025-10-10",
                    "notes": "Internal note"
                }
            ],
            "order_items.csv": [
                {
                    "order_id": "10",
                    "product_id": "100",
                    "quantity": "2"
                }
            ],
            "products.csv": [
                {
                    "product_id": "100",
                    "name": "Test Guitar"
                }
            ]
        }

        patcher = patch(
            "src.tools.orders.load_csv",
            side_effect=lambda filename: self.data[filename]
        )

        self.addCleanup(patcher.stop)
        patcher.start()

    def test_valid_order_lookup(self):
        result = get_order_status(
            10, "customer@example.com"
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "shipped")

    def test_invalid_email(self):
        result = get_order_status(
            10, "wrong@example.com"
        )

        self.assertFalse(result["success"])

    def test_unknown_order(self):
        result = get_order_status(
            999, "customer@example.com"
        )

        self.assertFalse(result["success"])

    def test_email_case_insensitive(self):
        result = get_order_status(
            10, "CUSTOMER@EXAMPLE.COM"
        )

        self.assertTrue(result["success"])

    def test_order_items(self):
        result = get_order_items(
            10, "customer@example.com"
        )

        self.assertTrue(result["success"])
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(
            result["items"][0]["product_name"],
            "Test Guitar"
        )

    def test_items_access_denied(self):
        result = get_order_items(
            10, "wrong@example.com"
        )

        self.assertFalse(result["success"])
        self.assertNotIn("items", result)

    def test_private_information_not_exposed(self):
        result = get_order_status(
            10, "customer@example.com"
        )

        self.assertNotIn("email", result)
        self.assertNotIn("notes", result)
        self.assertNotIn("customer_id", result)

    def test_invalid_order_id(self):
        result = get_order_status(
            -1, "customer@example.com"
        )

        self.assertFalse(result["success"])


if __name__ == "__main__":
    unittest.main()
