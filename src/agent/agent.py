
import inspect
import json
import os
import re

from dotenv import load_dotenv
from openai import OpenAI

from src.agent.prompts import SYSTEM_PROMPT

from src.tools.catalog import search_products

from src.tools.promotions import (
    get_active_promotions,
    get_product_promotion,
)

from src.tools.orders import (
    get_order_status,
    get_order_items,
)

from src.tools.comparison import (
    compare_products,
    format_comparison,
    parse_comparison_request,
)

from src.retrieval.policy_retriever import search_policies


load_dotenv()


# ==========================================================
# AVAILABLE TOOLS
# ==========================================================

TOOL_FUNCTIONS = {
    "search_products": search_products,
    "get_active_promotions": get_active_promotions,
    "get_product_promotion": get_product_promotion,
    "get_order_status": get_order_status,
    "get_order_items": get_order_items,
    "search_policies": search_policies,
    "compare_products": compare_products,
}


def tool_schema(name, description, properties, required=None):
    """Build a function calling schema."""

    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required or [],
                "additionalProperties": False,
            },
        },
    }


TOOLS = [
    tool_schema(
        "search_products",
        (
            "Search the store's product catalog by name, "
            "category, price and availability. "
            "Use this tool for questions about instruments, "
            "prices and stock. "
            "The query can contain Portuguese keywords such "
            "as 'violão', 'guitarra' or a product name. "
            "Use only_available=true for available products."
        ),
        {
            "query": {
                "type": "string",
                "description": "Product name or category keyword.",
            },
            "category": {
                "type": "string",
                "description": "Product category in Portuguese.",
            },
            "max_price": {
                "type": "number",
                "description": "Maximum product price in BRL.",
            },
            "only_available": {
                "type": "boolean",
                "description": "Return available products only.",
            },
        },
    ),

    tool_schema(
        "get_active_promotions",
        (
            "Retrieve active promotions, original prices, "
            "discount percentages and promotional prices."
        ),
        {},
    ),

    tool_schema(
        "get_product_promotion",
        "Find an active promotion for a specific product ID.",
        {
            "product_id": {
                "type": "integer",
                "description": "Numeric product identifier.",
            },
        },
        ["product_id"],
    ),

    tool_schema(
        "get_order_status",
        (
            "Retrieve an order's status after matching "
            "its ID and registered customer email. "
            "Both values must be provided by the customer."
        ),
        {
            "order_id": {
                "type": "integer",
                "description": "Numeric order identifier.",
            },
            "customer_email": {
                "type": "string",
                "description": "Email registered for the order.",
            },
        },
        ["order_id", "customer_email"],
    ),

    tool_schema(
        "get_order_items",
        (
            "Retrieve products from an order after matching "
            "its ID and registered customer email."
        ),
        {
            "order_id": {
                "type": "integer",
            },
            "customer_email": {
                "type": "string",
            },
        },
        ["order_id", "customer_email"],
    ),

    tool_schema(
        "search_policies",
        (
            "Search the store policy manual. "
            "Required for questions about returns, refunds, "
            "exchanges, shipping, payments, warranties "
            "and opening hours."
        ),
        {
            "query": {
                "type": "string",
                "description": "Question about store policies.",
            },
            "top_k": {
                "type": "integer",
                "description": "Number of passages to retrieve.",
            },
        },
        ["query"],
    ),

    tool_schema(
        "compare_products",
        (
            "Compare two specific instruments using verified "
            "catalog specifications, prices and availability. "
            "Do not infer sound quality or product superiority."
        ),
        {
            "product_a": {
                "type": "string",
                "description": "First product name.",
            },
            "product_b": {
                "type": "string",
                "description": "Second product name.",
            },
        },
        ["product_a", "product_b"],
    ),
]


# ==========================================================
# TOOL EXECUTION
# ==========================================================

def execute_tool(name: str, arguments: dict) -> str:
    """Execute an approved tool and serialize the result."""

    function = TOOL_FUNCTIONS.get(name)

    if function is None:
        return json.dumps({
            "error": "Unknown tool"
        })

    if not isinstance(arguments, dict):
        return json.dumps({
            "error": "Invalid tool arguments"
        })

    try:
        signature = inspect.signature(function)

        filtered_arguments = {
            key: value
            for key, value in arguments.items()
            if key in signature.parameters
        }

        result = function(**filtered_arguments)

        return json.dumps(
            result,
            ensure_ascii=False,
            default=str,
        )

    except (TypeError, ValueError, FileNotFoundError):
        return json.dumps({
            "error": "Tool execution failed",
            "message": "Please check the supplied parameters.",
        })


# ==========================================================
# RESPONSE VALIDATION
# ==========================================================

def is_invalid_response(response: str) -> bool:
    """Detect placeholders and incomplete generated responses."""

    if not response or not response.strip():
        return True

    invalid_patterns = [
        r"\[Product\s*\d+\]",
        r"\[Description\]",
        r"\[Product Name\]",
        r"\[Price\]",
        r"\[Nome do Produto\]",
        r"\[Descrição\]",
        r"and so on for all",
    ]

    return any(
        re.search(pattern, response, re.IGNORECASE)
        for pattern in invalid_patterns
    )


# ==========================================================
# AI AGENT
# ==========================================================

class MusicStoreAgent:
    """Local conversational agent using Ollama and tool calling."""

    def __init__(self, client=None, model=None):

        self.client = (
            client if client is not None else OpenAI(
                base_url=os.getenv(
                    "OLLAMA_BASE_URL",
                    "http://localhost:11434/v1",
                ),
                api_key="ollama",
                timeout=120.0,
            )
        )

        self.model = model or os.getenv(
            "OLLAMA_MODEL",
            "qwen3:4b",
        )

        self.messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            }
        ]

    # ======================================================
    # MODEL GENERATION
    # ======================================================

    def _generate_response(self, messages, use_tools=True):
        """Generate an LLM response using Ollama."""

        parameters = {
            "model": self.model,
            "messages": messages,
            "temperature": 0,
            "extra_body": {
                "think": False,
                "options": {
                    "num_predict": 1024,
                },
            },
        }

        if use_tools:
            parameters["tools"] = TOOLS
            parameters["tool_choice"] = "auto"

        return self.client.chat.completions.create(
            **parameters
        )

    # ======================================================
    # INVALID RESPONSE RETRY
    # ======================================================

    def _retry_invalid_response(
        self,
        messages,
        invalid_answer
    ):
        """Retry an invalid response using retrieved evidence."""

        retry_messages = list(messages)

        retry_messages.append({
            "role": "assistant",
            "content": invalid_answer,
        })

        retry_messages.append({
            "role": "user",
            "content": (
                "Sua resposta anterior está incompleta ou "
                "contém placeholders. Corrija a resposta. "
                "Responda somente em português brasileiro. "
                "Utilize exclusivamente os dados reais "
                "retornados pelas ferramentas anteriores. "
                "Não invente nomes, preços, características "
                "ou disponibilidade de produtos. "
                "Não utilize placeholders. "
                "Se houver vários produtos, apresente "
                "de 3 a 5 opções verificadas."
            ),
        })

        response = self._generate_response(
            retry_messages,
            use_tools=False,
        )

        answer = (
            response.choices[0].message.content or ""
        )

        if is_invalid_response(answer):
            return (
                "Não consegui apresentar as informações "
                "com segurança neste momento. "
                "Pode tentar reformular sua pergunta?"
            )

        return answer

    # ======================================================
    # DETERMINISTIC PRODUCT COMPARISON
    # ======================================================

    def _handle_product_comparison(
        self,
        user_message: str
    ) -> str | None:
        """Handle explicit product comparisons with catalog data."""

        comparison_request = parse_comparison_request(
            user_message
        )

        if comparison_request is None:
            return None

        product_a, product_b = comparison_request

        comparison = compare_products(
            product_a,
            product_b,
        )

        if not comparison["success"]:
            return None

        answer = format_comparison(comparison)

        # Register the actual local execution in conversation
        # history using the same structure as tool calling.
        call_id = f"local_comparison_{len(self.messages)}"

        arguments = json.dumps(
            {
                "product_a": product_a,
                "product_b": product_b,
            },
            ensure_ascii=False,
        )

        self.messages.extend([
            {
                "role": "user",
                "content": user_message,
            },
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": call_id,
                        "type": "function",
                        "function": {
                            "name": "compare_products",
                            "arguments": arguments,
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": call_id,
                "content": json.dumps(
                    comparison,
                    ensure_ascii=False,
                    default=str,
                ),
            },
            {
                "role": "assistant",
                "content": answer,
            },
        ])

        print("\n[Tool called: compare_products]")
        print("[Comparison based on catalog specifications]")

        return answer

    # ======================================================
    # MAIN CONVERSATION FLOW
    # ======================================================

    def chat(self, user_message: str) -> str:
        """Process a customer message and execute tool calls."""

        if not user_message.strip():
            return "Por favor, escreva sua pergunta."

        # Handle explicit comparisons deterministically.
        comparison_answer = self._handle_product_comparison(
            user_message
        )

        if comparison_answer is not None:
            return comparison_answer

        # Work with a copy to preserve the current history
        # if model execution fails.
        messages = list(self.messages)

        messages.append({
            "role": "user",
            "content": user_message,
        })

        max_iterations = 5

        for _ in range(max_iterations):

            response = self._generate_response(
                messages,
                use_tools=True,
            )

            assistant_message = (
                response.choices[0].message
            )

            # --------------------------------------------------
            # FINAL RESPONSE
            # --------------------------------------------------

            if not assistant_message.tool_calls:

                answer = assistant_message.content or ""

                if is_invalid_response(answer):
                    answer = self._retry_invalid_response(
                        messages,
                        answer,
                    )

                messages.append({
                    "role": "assistant",
                    "content": answer,
                })

                self.messages = messages

                return answer

            # --------------------------------------------------
            # TOOL CALLS
            # --------------------------------------------------

            messages.append(
                assistant_message.model_dump(
                    exclude_none=True
                )
            )

            for tool_call in assistant_message.tool_calls:

                tool_name = tool_call.function.name
                arguments = {}

                try:
                    arguments = json.loads(
                        tool_call.function.arguments
                    )

                    if not isinstance(arguments, dict):
                        raise ValueError(
                            "Tool arguments must be a JSON object"
                        )

                    result = execute_tool(
                        tool_name,
                        arguments,
                    )

                except (ValueError, TypeError):
                    result = json.dumps({
                        "error": "Invalid tool arguments"
                    })

                print(f"\n[Tool called: {tool_name}]")

                if tool_name in {
                    "get_order_status",
                    "get_order_items",
                }:
                    print("[Arguments: redacted]")
                    print("[Tool result: redacted]")
                else:
                    print(f"[Arguments: {arguments}]")
                    print(f"[Tool result: {result[:3000]}]")

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                })

        # Do not preserve incomplete model interactions.
        return (
            "Não consegui concluir a consulta. "
            "Por favor, tente reformular sua pergunta."
        )
