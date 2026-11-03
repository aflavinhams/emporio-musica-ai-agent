
import json
import unittest
from unittest.mock import MagicMock, patch

from src.agent.agent import (
    MusicStoreAgent,
    return_receipt_state,
    is_refund_action_request,
    has_return_policy_evidence,
)


POLICY_PASSAGES = [
    {
        "page": 4,
        "content": (
            "Direito de Arrependimento: o cliente pode solicitar "
            "devolução em até 7 dias corridos após o recebimento "
            "do produto, com embalagem original e sem sinais "
            "de uso. O frete de devolução é pago pela loja. "
            "Reembolso pela forma original em até 10 dias úteis."
        ),
        "score": 0.8,
    }
]


class TestReturnSafety(unittest.TestCase):

    def setUp(self):
        self.client = MagicMock()
        self.agent = MusicStoreAgent(
            client=self.client,
            model="test-model",
        )

    def test_purchase_date_without_receipt_date(self):
        message = (
            "Comprei um violão online há 5 dias. "
            "Posso devolver?"
        )

        self.assertEqual(
            return_receipt_state(message),
            "unknown",
        )

    def test_explicit_receipt_date(self):
        message = (
            "Comprei há 5 dias e recebi há 2 dias. "
            "Posso devolver?"
        )

        self.assertIsNone(return_receipt_state(message))

    def test_product_not_received(self):
        message = (
            "Comprei um violão há 5 dias, "
            "mas ainda não recebi. Posso devolver?"
        )

        self.assertEqual(
            return_receipt_state(message),
            "not_received",
        )

    def test_policy_evidence_required(self):
        self.assertTrue(
            has_return_policy_evidence(POLICY_PASSAGES)
        )

        self.assertFalse(
            has_return_policy_evidence([
                {
                    "page": 3,
                    "content": "Pagamento via cartão.",
                }
            ])
        )

    def test_no_delivery_date_inference(self):
        message = (
            "Comprei um violão online há 5 dias. "
            "Posso devolver?"
        )

        with patch(
            "src.agent.agent.execute_tool",
            return_value=json.dumps(
                POLICY_PASSAGES,
                ensure_ascii=False,
            ),
        ):
            answer = self.agent.chat(message)

        self.assertIn("recebimento", answer)
        self.assertIn("Há quantos dias", answer)
        self.assertNotIn("você ainda está dentro", answer)

        # The deterministic rule does not call the LLM.
        self.client.chat.completions.create.assert_not_called()

    def test_refund_action_blocked(self):
        message = (
            "Vocês conseguem fazer a devolução "
            "e o reembolso diretamente por aqui?"
        )

        self.assertTrue(is_refund_action_request(message))

        answer = self.agent.chat(message)

        self.assertIn("não consigo", answer)
        self.assertIn("atendimento", answer)

        self.client.chat.completions.create.assert_not_called()

    def test_general_return_question_not_blocked(self):
        self.assertFalse(
            is_refund_action_request(
                "Comprei há 5 dias. Posso devolver?"
            )
        )


if __name__ == "__main__":
    unittest.main()
