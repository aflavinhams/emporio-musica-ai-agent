
import unittest

from src.tools.catalog import (
    matches_search,
    search_products,
)


class TestCatalogSearchVariants(unittest.TestCase):

    def test_electric_guitar_plural(self):
        """Plural electric guitar query finds catalog guitars."""

        results = search_products(
            query="guitarras elétricas",
            only_available=True,
        )

        self.assertGreater(len(results), 0)

        self.assertTrue(
            all(
                product["category"] == "Guitarras"
                for product in results
            )
        )

    def test_electric_guitar_singular(self):
        """Singular and plural queries return the same products."""

        singular = search_products(
            query="guitarra elétrica",
            only_available=True,
        )

        plural = search_products(
            query="guitarras elétricas",
            only_available=True,
        )

        self.assertEqual(
            [item["product_id"] for item in singular],
            [item["product_id"] for item in plural],
        )

    def test_guitar_category_alias(self):
        """Category and electric guitar queries are equivalent."""

        guitars = search_products(
            query="guitarras",
            only_available=True,
        )

        electric_guitars = search_products(
            query="guitarras elétricas",
            only_available=True,
        )

        self.assertEqual(guitars, electric_guitars)

    def test_price_filter_is_preserved(self):
        """Flexible queries must still respect maximum price."""

        results = search_products(
            query="guitarras elétricas",
            max_price=6000,
            only_available=True,
        )

        self.assertTrue(
            all(
                product["price_brl"] <= 6000
                for product in results
            )
        )

    def test_product_name_matching(self):
        """Specific product names must remain searchable."""

        self.assertTrue(
            matches_search(
                "Fender Telecaster Player Series",
                "Guitarras",
                "guitarra elétrica Fender",
            )
        )

        self.assertFalse(
            matches_search(
                "Yamaha C40 Nylon Natural",
                "Violões",
                "guitarras elétricas",
            )
        )


if __name__ == "__main__":
    unittest.main()
