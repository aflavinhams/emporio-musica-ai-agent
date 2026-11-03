
import unittest

from src.tools.comparison import (
    compare_products,
    format_comparison,
    parse_comparison_request,
)


class TestComparison(unittest.TestCase):

    def test_valid_comparison(self):
        """Verify comparison between two existing products."""
        result = compare_products(
            "Yamaha C40",
            "Tagima Memphis AC-39",
        )

        self.assertTrue(result["success"])
        self.assertEqual(
            result["price_difference_brl"],
            170.0,
        )

    def test_real_specifications(self):
        """Verify specifications from the actual catalog."""
        result = compare_products(
            "Yamaha C40",
            "Tagima Memphis AC-39",
        )

        self.assertTrue(result["success"])

        self.assertEqual(
            result["first"]["specifications"]["top"],
            "Spruce",
        )

        self.assertEqual(
            result["second"]["specifications"]["top"],
            "Linden",
        )

    def test_unknown_product(self):
        """Reject comparisons with unknown products."""
        result = compare_products(
            "Unknown Model",
            "Yamaha C40",
        )

        self.assertFalse(result["success"])

    def test_no_unsupported_superiority(self):
        """Avoid unsupported product quality claims."""
        result = compare_products(
            "Yamaha C40",
            "Tagima Memphis AC-39",
        )

        answer = format_comparison(result)

        self.assertIn("R$ 170,00", answer)
        self.assertIn(
            "Não é possível afirmar",
            answer,
        )

    def test_parse_comparison_request(self):
        """Recognize a product comparison request."""
        result = parse_comparison_request(
            "Qual a diferença entre o Yamaha C40 "
            "e o Tagima Memphis AC-39?"
        )

        self.assertEqual(
            result,
            ("Yamaha C40", "Tagima Memphis AC-39"),
        )


if __name__ == "__main__":
    unittest.main()
