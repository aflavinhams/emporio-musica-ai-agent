
import json
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.agent.agent import (
    MusicStoreAgent,
    is_policy_question,
    is_invalid_response,
    build_policy_query,
)


def make_response(content):
    """Simulate a plain LLM response."""
    message = MagicMock()
    message.content = content
    message.tool_calls = None

    return SimpleNamespace(
        choices=[
            SimpleNamespace(message=message)
        ]
    )


class TestPolicyRouting(unittest.TestCase):

    def setUp(self):
        self.client = MagicMock()
        self.agent = MusicStoreAgent(
            client=self.client,
            model="test-model",
        )

    def test_pix_requires_policy(self):
        self.assertTrue(
            is_policy_question(
                "Se eu pagar no PIX, consigo mais 5%?"
            )
        )

    def test_return_requires_policy(self):
        self.assertTrue(
            is_policy_question(
                "Posso devolver um violão?"
            )
        )

    def test_product_search_not_policy(self):
        self.assertFalse(
            is_policy_question(
                "Quais violões custam até R$ 800?"
            )
        )

    def test_order_tracking_not_policy(self):
        self.assertFalse(
            is_policy_question(
                "Quero rastrear meu pedido."
            )
        )

    def test_pix_query_contains_discount_terms(self):
        query = build_policy_query(
            "Posso pagar no PIX?"
        )

        self.assertIn("não cumulativas", query)

    def test_policy_tool_runs_before_response(self):
        self.client.chat.completions.create.return_value = (
            make_response(
                "O desconto PIX não é cumulativo com promoções."
            )
        )

        passages = [
            {
                "page": 6,
                "content": (
                    "Promoções não são cumulativas "
                    "com o desconto do PIX."
                ),
                "score": 0.5,
            }
        ]

        events = []

        def fake_tool(name, arguments):
            events.append("policy")
            self.assertEqual(name, "search_policies")
            return json.dumps(passages)

        def fake_generation(**kwargs):
            events.append("llm")
            return make_response(
                "O desconto PIX não é cumulativo com promoções."
            )

        self.client.chat.completions.create.side_effect = (
            fake_generation
        )

        with patch(
            "src.agent.agent.execute_tool",
            side_effect=fake_tool,
        ):
            answer = self.agent.chat(
                "Se eu pagar no PIX, consigo mais 5%?"
            )

        self.assertEqual(events, ["policy", "llm"])
        self.assertIn("não é cumulativo", answer)

        tool_messages = [
            message
            for message in self.agent.messages
            if message["role"] == "tool"
        ]

        self.assertEqual(len(tool_messages), 1)

    def test_missing_policy_evidence_blocks_answer(self):
        with patch(
            "src.agent.agent.execute_tool",
            return_value="[]",
        ):
            answer = self.agent.chat(
                "Quais são as condições de pagamento?"
            )

        self.assertIn(
            "Não consegui consultar as políticas",
            answer,
        )

        self.client.chat.completions.create.assert_not_called()

    def test_checkout_offer_is_invalid(self):
        self.assertTrue(
            is_invalid_response(
                "Quer saber mais detalhes ou confirmar a compra?"
            )
        )

    def test_legitimate_checkout_limitation_is_valid(self):
        self.assertFalse(
            is_invalid_response(
                "Não consigo finalizar compras por aqui."
            )
        )


if __name__ == "__main__":
    unittest.main()
