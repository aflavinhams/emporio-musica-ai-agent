
import unittest

from src.retrieval.policy_retriever import (
    search_policies,
    split_text,
)


class TestPolicyRetriever(unittest.TestCase):

    def test_text_splitting(self):
        text = "This is an example. " * 100

        chunks = split_text(
            text,
            chunk_size=200,
            overlap=40
        )

        self.assertGreater(len(chunks), 1)
        self.assertTrue(
            all(len(chunk) <= 200 for chunk in chunks)
        )

    def test_returns_page_references(self):
        results = search_policies(
            "Qual o horario de funcionamento da loja?"
        )

        self.assertTrue(results)
        self.assertIn("page", results[0])
        self.assertIn("content", results[0])
        self.assertIn("score", results[0])

    def test_returns_relevant_return_policy(self):
        results = search_policies(
            "Posso devolver uma compra online por arrependimento?"
        )

        self.assertTrue(results)
        self.assertEqual(results[0]["page"], 4)

    def test_empty_query(self):
        results = search_policies("")

        self.assertEqual(results, [])

    def test_results_limit(self):
        results = search_policies(
            "Quais as regras de pagamento?",
            top_k=2
        )

        self.assertLessEqual(len(results), 2)

    def test_invalid_top_k(self):
        with self.assertRaises(ValueError):
            search_policies(
                "Qual o horário da loja?",
                top_k=0
            )


if __name__ == "__main__":
    unittest.main()
