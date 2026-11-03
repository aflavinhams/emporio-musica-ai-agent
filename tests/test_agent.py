
import json
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.agent.agent import (
    MusicStoreAgent,
    execute_tool,
    is_invalid_response,
)


def make_tool_call(name, arguments, call_id="call_1"):
    """Create a simulated OpenAI tool call."""

    return SimpleNamespace(
        id=call_id,
        type="function",
        function=SimpleNamespace(
            name=name,
            arguments=arguments,
        ),
    )


def make_response(content=None, tool_calls=None):
    """Create a simulated LLM response."""

    message = MagicMock()
    message.content = content
    message.tool_calls = tool_calls

    message.model_dump.return_value = {
        "role": "assistant",
        "content": content,
        "tool_calls": [
            {
                "id": call.id,
                "type": "function",
                "function": {
                    "name": call.function.name,
                    "arguments": call.function.arguments,
                },
            }
            for call in (tool_calls or [])
        ],
    }

    return SimpleNamespace(
        choices=[
            SimpleNamespace(message=message)
        ]
    )


class TestAgent(unittest.TestCase):
    """Unit tests for the conversational agent."""

    def setUp(self):
        self.client = MagicMock()

        self.agent = MusicStoreAgent(
            client=self.client,
            model="test-model",
        )

    def set_responses(self, *responses):
        """Configure consecutive simulated LLM responses."""

        self.client.chat.completions.create.side_effect = (
            list(responses)
        )

    # ======================================================
    # BASIC CONVERSATION
    # ======================================================

    def test_empty_message(self):
        """Empty messages should not invoke the model."""

        answer = self.agent.chat("   ")

        self.assertIn(
            "Por favor, escreva sua pergunta",
            answer,
        )

        self.client.chat.completions.create.assert_not_called()

    def test_normal_response(self):
        """A regular response should be saved in history."""

        self.set_responses(
            make_response("Olá! Como posso ajudar?")
        )

        answer = self.agent.chat("Oi!")

        self.assertEqual(
            answer,
            "Olá! Como posso ajudar?",
        )

        self.assertEqual(
            self.agent.messages[-1]["role"],
            "assistant",
        )

        self.assertEqual(
            self.agent.messages[-1]["content"],
            answer,
        )

    # ======================================================
    # RESPONSE VALIDATION
    # ======================================================

    def test_invalid_response_retry(self):
        """Malformed output should trigger a correction."""

        self.set_responses(
            make_response("[Product 1]"),
            make_response(
                "Posso ajudar a encontrar um violão."
            ),
        )

        answer = self.agent.chat(
            "Olá! Preciso de ajuda."
        )

        self.assertEqual(
            answer,
            "Posso ajudar a encontrar um violão.",
        )

        self.assertEqual(
            self.client.chat.completions.create.call_count,
            2,
        )

    def test_invalid_response_detection(self):
        """Placeholder and raw tool-call responses are invalid."""

        self.assertTrue(
            is_invalid_response("[Product 1]")
        )

        self.assertTrue(
            is_invalid_response(
                '{"name": "search_products", "arguments": {}}'
            )
        )

        self.assertFalse(
            is_invalid_response(
                "Temos violões disponíveis no catálogo."
            )
        )

    # ======================================================
    # TOOL SAFETY
    # ======================================================

    def test_unknown_tool(self):
        """Tools outside the allowlist must be rejected."""

        result = json.loads(
            execute_tool(
                "delete_all_orders",
                {},
            )
        )

        self.assertEqual(
            result["error"],
            "Unknown tool",
        )

    def test_invalid_tool_arguments(self):
        """Tool arguments must be dictionaries."""

        result = json.loads(
            execute_tool(
                "search_products",
                ["invalid"],
            )
        )

        self.assertEqual(
            result["error"],
            "Invalid tool arguments",
        )

    # ======================================================
    # CATALOG
    # ======================================================

    def test_catalog_response_uses_verified_data(self):
        """Catalog results should be formatted without another LLM call."""

        call = make_tool_call(
            "search_products",
            json.dumps({
                "query": "violão",
                "max_price": 800,
            }),
        )

        self.set_responses(
            make_response(tool_calls=[call])
        )

        products = [
            {
                "name": "Yamaha C40 Nylon Natural",
                "price_brl": 599.90,
                "stock_quantity": 12,
                "description": "Violão com cordas de nylon.",
            },
        ]

        with patch(
            "src.agent.agent.execute_tool",
            return_value=json.dumps(
                products,
                ensure_ascii=False,
            ),
        ):
            answer = self.agent.chat(
                "Quais violões custam até R$ 800?"
            )

        self.assertIn(
            "Yamaha C40 Nylon Natural",
            answer,
        )

        self.assertIn(
            "R$ 599,90",
            answer,
        )

        self.assertIn(
            "12 unidades",
            answer,
        )

        self.assertEqual(
            self.client.chat.completions.create.call_count,
            1,
        )

    # ======================================================
    # ORDER TOOLS
    # ======================================================

    def test_order_tool_execution(self):
        """Order tool results should be returned to the model."""

        call = make_tool_call(
            "get_order_status",
            json.dumps({
                "order_id": 1,
                "customer_email": "cliente@example.com",
            }),
        )

        self.set_responses(
            make_response(tool_calls=[call]),
            make_response(
                "O pedido consta como entregue."
            ),
        )

        with patch(
            "src.agent.agent.execute_tool",
            return_value=json.dumps({
                "order_id": 1,
                "status": "delivered",
            }),
        ) as tool_mock:
            answer = self.agent.chat(
                "Qual é o status do pedido 1?"
            )

        self.assertIn(
            "entregue",
            answer,
        )

        tool_mock.assert_called_once()

        self.assertEqual(
            tool_mock.call_args.args[0],
            "get_order_status",
        )

    # ======================================================
    # POLICY RETRIEVAL
    # ======================================================

    def test_missing_policy_evidence(self):
        """The agent should not invent policies when retrieval fails."""

        with patch(
            "src.agent.agent.execute_tool",
            return_value="[]",
        ):
            answer = self.agent.chat(
                "Qual é a política de garantia?"
            )

        self.assertIn(
            "Não consegui consultar as políticas",
            answer,
        )

        self.client.chat.completions.create.assert_not_called()

    # ======================================================
    # TOOL CYCLE LIMIT
    # ======================================================

    def test_tool_call_limit(self):
        """Stop after the maximum number of tool cycles."""

        responses = []

        for index in range(5):
            call = make_tool_call(
                "get_active_promotions",
                "{}",
                call_id=f"call_{index}",
            )

            responses.append(
                make_response(tool_calls=[call])
            )

        self.set_responses(*responses)

        with patch(
            "src.agent.agent.execute_tool",
            return_value="[]",
        ):
            answer = self.agent.chat(
                "Quais instrumentos estão em promoção?"
            )

        self.assertIn(
            "Não consegui concluir",
            answer,
        )

        self.assertEqual(
            self.client.chat.completions.create.call_count,
            5,
        )


if __name__ == "__main__":
    unittest.main()
