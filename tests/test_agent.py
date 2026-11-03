
import json
import unittest

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.agent.agent import (
    MusicStoreAgent,
    execute_tool,
)


# ==========================================================
# MOCK HELPERS
# ==========================================================

def make_tool_call(name, arguments, call_id="call_1"):
    """Create a simulated LLM tool call."""

    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(
            name=name,
            arguments=arguments,
        ),
    )


def make_response(content=None, tool_calls=None):
    """Create a simulated Chat Completions response."""

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


# ==========================================================
# AGENT TESTS
# ==========================================================

class TestAgent(unittest.TestCase):

    def setUp(self):
        """Initialize the agent without connecting to Ollama."""

        self.client = MagicMock()

        self.agent = MusicStoreAgent(
            client=self.client,
            model="test-model",
        )

    def set_responses(self, *responses):
        """Configure simulated LLM responses."""

        self.client.chat.completions.create.side_effect = (
            list(responses)
        )

    # ------------------------------------------------------
    # SIMPLE RESPONSE
    # ------------------------------------------------------

    def test_simple_response(self):
        """Verify a response that does not require tools."""

        self.set_responses(
            make_response(
                content="Olá! Como posso ajudar?"
            )
        )

        answer = self.agent.chat("Oi")

        self.assertEqual(
            answer,
            "Olá! Como posso ajudar?"
        )

        self.client.chat.completions.create.assert_called_once()

    # ------------------------------------------------------
    # PRODUCT TOOL EXECUTION
    # ------------------------------------------------------

    def test_product_tool_execution(self):
        """Verify deterministic product response after tool execution."""

        call = make_tool_call(
            "search_products",
            json.dumps({
                "query": "violão",
                "max_price": 800,
            }),
        )

        self.set_responses(
            make_response(tool_calls=[call]),
        )

        fake_products = [
            {
                "product_id": 83,
                "name": "Tagima Memphis AC-39 Nylon Natural",
                "price_brl": 429.90,
                "stock_quantity": 15,
                "description": "Violão para iniciantes.",
            }
        ]

        with patch(
            "src.agent.agent.execute_tool",
            return_value=json.dumps(fake_products),
        ) as mock_execute:

            answer = self.agent.chat(
                "Quais violões custam até R$ 800?"
            )

            mock_execute.assert_called_once_with(
                "search_products",
                {
                    "query": "violão",
                    "max_price": 800,
                },
            )

        self.assertIn(
            "Tagima Memphis AC-39",
            answer,
        )

        self.assertIn(
            "R$ 429,90",
            answer,
        )

        self.assertEqual(
            self.client.chat.completions.create.call_count,
            1,
        )

    # ------------------------------------------------------
    # HALLUCINATION PREVENTION
    # ------------------------------------------------------

    def test_catalog_never_uses_hallucinated_response(self):
        """Ensure catalog answers are based on tool results."""

        call = make_tool_call(
            "search_products",
            json.dumps({
                "query": "violão",
                "max_price": 800,
            }),
        )

        hallucinated_response = make_response(
            content="Violão fictício - R$ 1.299,50"
        )

        self.set_responses(
            make_response(tool_calls=[call]),
            hallucinated_response,
        )

        fake_products = [
            {
                "product_id": 83,
                "name": "Tagima Memphis AC-39 Nylon Natural",
                "price_brl": 429.90,
                "stock_quantity": 15,
                "description": "Violão para iniciantes.",
            }
        ]

        with patch(
            "src.agent.agent.execute_tool",
            return_value=json.dumps(fake_products),
        ):
            answer = self.agent.chat(
                "Quais violões vocês têm até R$ 800?"
            )

        self.assertIn(
            "Tagima Memphis AC-39",
            answer,
        )

        self.assertIn(
            "R$ 429,90",
            answer,
        )

        self.assertNotIn(
            "Violão fictício",
            answer,
        )

        self.assertNotIn(
            "R$ 1.299,50",
            answer,
        )

        self.assertEqual(
            self.client.chat.completions.create.call_count,
            1,
        )

    # ------------------------------------------------------
    # CONVERSATION HISTORY
    # ------------------------------------------------------

    def test_conversation_history(self):
        """Verify history is maintained across messages."""

        self.set_responses(
            make_response(content="Olá!"),
            make_response(content="Claro!"),
        )

        self.agent.chat("Oi")
        self.agent.chat("Pode me ajudar?")

        messages = self.agent.messages

        self.assertEqual(len(messages), 5)

        self.assertEqual(
            messages[1]["content"],
            "Oi",
        )

        self.assertEqual(
            messages[2]["content"],
            "Olá!",
        )

        self.assertEqual(
            messages[3]["content"],
            "Pode me ajudar?",
        )

    # ------------------------------------------------------
    # INVALID JSON ARGUMENTS
    # ------------------------------------------------------

    def test_invalid_json_arguments(self):
        """Verify malformed tool arguments are handled."""

        call = make_tool_call(
            "search_products",
            "{invalid_json",
        )

        self.set_responses(
            make_response(tool_calls=[call]),
            make_response(
                content="Não consegui consultar."
            ),
        )

        answer = self.agent.chat("Buscar produtos")

        self.assertEqual(
            answer,
            "Não consegui consultar.",
        )

        tool_messages = [
            message
            for message in self.agent.messages
            if message["role"] == "tool"
        ]

        self.assertEqual(
            len(tool_messages),
            1,
        )

        self.assertIn(
            "Invalid tool arguments",
            tool_messages[0]["content"],
        )

    # ------------------------------------------------------
    # UNKNOWN TOOL
    # ------------------------------------------------------

    def test_unknown_tool(self):
        """Reject tools outside the allowlist."""

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

    # ------------------------------------------------------
    # TOOL EXECUTION ERROR
    # ------------------------------------------------------

    def test_tool_execution_error(self):
        """Verify tool errors are handled safely."""

        with patch(
            "src.agent.agent.search_products",
            side_effect=ValueError("Invalid price"),
        ):
            # Patch the function in the allowlist itself.
            with patch.dict(
                "src.agent.agent.TOOL_FUNCTIONS",
                {
                    "search_products": (
                        lambda max_price=-100: (
                            (_ for _ in ()).throw(
                                ValueError("Invalid price")
                            )
                        )
                    )
                },
            ):
                result = json.loads(
                    execute_tool(
                        "search_products",
                        {"max_price": -100},
                    )
                )

        self.assertEqual(
            result["error"],
            "Tool execution failed",
        )

    # ------------------------------------------------------
    # TOOL CALL LIMIT
    # ------------------------------------------------------

    def test_tool_call_limit(self):
        """Stop after the maximum number of tool cycles."""

        responses = []

        for index in range(5):
            call = make_tool_call(
                "search_policies",
                json.dumps({"query": "horário"}),
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
                "Qual o horário de funcionamento?"
            )

        self.assertIn(
            "Não consegui concluir",
            answer,
        )

        self.assertEqual(
            self.client.chat.completions.create.call_count,
            5,
        )

    # ------------------------------------------------------
    # API FAILURE
    # ------------------------------------------------------

    def test_api_failure_preserves_history(self):
        """Do not save a failed conversation turn."""

        original_messages = list(self.agent.messages)

        self.client.chat.completions.create.side_effect = (
            RuntimeError("Connection unavailable")
        )

        with self.assertRaises(RuntimeError):
            self.agent.chat("Olá")

        self.assertEqual(
            self.agent.messages,
            original_messages,
        )

    # ------------------------------------------------------
    # EMPTY MESSAGE
    # ------------------------------------------------------

    def test_empty_message(self):
        """Handle blank user input without calling the LLM."""

        answer = self.agent.chat("   ")

        self.assertEqual(
            answer,
            "Por favor, escreva sua pergunta.",
        )

        self.client.chat.completions.create.assert_not_called()


if __name__ == "__main__":
    unittest.main()
