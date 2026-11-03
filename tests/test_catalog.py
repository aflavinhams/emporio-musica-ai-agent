
import unittest

from src.tools.catalog import search_products


class TestCatalog(unittest.TestCase):

    def test_search_by_category_keyword(self):
        products = search_products(
            query="violões",
            max_price=1000
        )

        self.assertTrue(products)

        self.assertTrue(
            all(
                product["category"] == "Violões"
                and product["price_brl"] <= 1000
                for product in products
            )
        )

    def test_price_limit(self):
        products = search_products(max_price=1000)

        self.assertTrue(products)
        self.assertTrue(
            all(product["price_brl"] <= 1000 for product in products)
        )

    def test_only_available_products(self):
        products = search_products()

        self.assertTrue(
            all(
                product["status"] == "active"
                and product["stock_quantity"] > 0
                for product in products
            )
        )

    def test_category_filter(self):
        products = search_products(
            category="Violões",
            max_price=1000
        )

        self.assertTrue(products)
        self.assertTrue(
            all(product["category"] == "Violões" for product in products)
        )

    def test_invalid_price(self):
        with self.assertRaises(ValueError):
            search_products(max_price=-100)


if __name__ == "__main__":
    unittest.main()
