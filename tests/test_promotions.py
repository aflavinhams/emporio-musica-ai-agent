
import unittest
from decimal import Decimal

from src.tools.catalog import load_csv
from src.tools.promotions import (
    calculate_discount,
    get_active_promotions,
    get_product_promotion,
)


class TestPromotions(unittest.TestCase):

    def test_discount_calculation(self):
        result = calculate_discount(
            Decimal("1000.00"),
            Decimal("20")
        )

        self.assertEqual(result, Decimal("800.00"))

    def test_only_active_promotions(self):
        active_ids = {
            int(row["promotion_id"])
            for row in load_csv("promotions.csv")
            if row["is_active"] == "1"
        }

        promotions = get_active_promotions()

        self.assertTrue(
            all(
                promotion["promotion_id"] in active_ids
                for promotion in promotions
            )
        )

    def test_product_must_be_available(self):
        promotions = get_active_promotions()

        self.assertTrue(
            all(
                promotion["stock_quantity"] > 0
                for promotion in promotions
            )
        )

    def test_promotional_price_is_lower(self):
        promotions = get_active_promotions()

        self.assertTrue(
            all(
                promotion["promotional_price_brl"]
                < promotion["original_price_brl"]
                for promotion in promotions
            )
        )

    def test_no_pix_discount_stacking(self):
        promotions = get_active_promotions()

        self.assertTrue(
            all(
                not promotion["pix_discount_applicable"]
                for promotion in promotions
            )
        )

    def test_product_promotion_lookup(self):
        promotions = get_active_promotions()

        if promotions:
            product_id = promotions[0]["product_id"]

            result = get_product_promotion(product_id)

            self.assertIsNotNone(result)
            self.assertEqual(result["product_id"], product_id)

    def test_unknown_product(self):
        result = get_product_promotion(-1)

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
