
import inspect
import json
import os
import re
from decimal import Decimal

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
            "Search musical instruments by name, category, "
            "maximum price and availability. "
            "Use for product recommendations and stock questions. "
            "Portuguese keywords such as 'violão' are accepted."
        ),
        {
            "query": {"type": "string"},
            "category": {"type": "string"},
            "max_price": {"type": "number"},
            "only_available": {"type": "boolean"},
        },
    ),
    tool_schema(
        "get_active_promotions",
        "Retrieve current promotions in the provided dataset.",
        {},
    ),
    tool_schema(
        "get_product_promotion",
        "Retrieve a promotion using a numeric product ID.",
        {"product_id": {"type": "integer"}},
        ["product_id"],
    ),
    tool_schema(
        "get_order_status",
        "Retrieve order status using order ID and registered email.",
        {
            "order_id": {"type": "integer"},
            "customer_email": {"type": "string"},
        },
        ["order_id", "customer_email"],
    ),
    tool_schema(
        "get_order_items",
        "Retrieve order items using order ID and registered email.",
        {
            "order_id": {"type": "integer"},
            "customer_email": {"type": "string"},
        },
        ["order_id", "customer_email"],
    ),
    tool_schema(
        "search_policies",
        (
            "Search the store policy PDF. Required for returns, "
            "refunds, payments, opening hours, warranties, "
            "shipping and exchanges."
        ),
        {
            "query": {"type": "string"},
            "top_k": {"type": "integer"},
        },
        ["query"],
    ),
    tool_schema(
        "compare_products",
        "Compare two products using catalog specifications.",
        {
            "product_a": {"type": "string"},
            "product_b": {"type": "string"},
        },
        ["product_a", "product_b"],
    ),
]


# ==========================================================
# TOOL EXECUTION
# ==========================================================

def execute_tool(name: str, arguments: dict) -> str:
    """Execute an allowlisted tool with validated arguments."""

    function = TOOL_FUNCTIONS.get(name)

    if function is None:
        return json.dumps({"error": "Unknown tool"})

    if not isinstance(arguments, dict):
        return json.dumps({"error": "Invalid tool arguments"})

    try:
        signature = inspect.signature(function)

        filtered = {
            key: value
            for key, value in arguments.items()
            if key in signature.parameters
        }

        result = function(**filtered)

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
    """Detect placeholders and tool calls exposed as text."""

    if not response or not response.strip():
        return True

    patterns = [
        r"\[Product\s*\d+\]",
        r"\[Description\]",
        r"\[Product Name\]",
        r"\[Price\]",
        r"\[Nome do Produto\]",
        r"\[Descrição\]",
        r"and so on for all",
    ]

    if any(
        re.search(pattern, response, re.IGNORECASE)
        for pattern in patterns
    ):
        return True

    try:
        parsed = json.loads(response.strip())

        if isinstance(parsed, dict):
            if "name" in parsed and "arguments" in parsed:
                return True
            if "function" in parsed and "arguments" in parsed:
                return True

    except json.JSONDecodeError:
        pass

    return False


# ==========================================================
# DETERMINISTIC CATALOG RESPONSE
# ==========================================================

def format_brl(value) -> str:
    """Format money in Brazilian reais."""

    amount = Decimal(str(value))
    formatted = f"{amount:,.2f}"

    formatted = (
        formatted.replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )

    return f"R$ {formatted}"


def format_catalog_response(products: list[dict]) -> str:
    """Generate a response using only verified catalog records."""

    if not products:
        return (
            "Não encontrei instrumentos disponíveis com "
            "os critérios informados. Quer tentar outro "
            "modelo ou uma faixa de preço diferente?"
        )

    lines = [
        "Olá! 😊 Encontrei estas opções no nosso catálogo:",
        "",
    ]

    for index, product in enumerate(products[:5], start=1):
        lines.append(
            f"{index}. {product['name']} - "
            f"{format_brl(product['price_brl'])}"
        )

        lines.append(
            f"   Estoque registrado: "
            f"{product['stock_quantity']} unidades"
        )

        if product.get("description"):
            lines.append(
                f"   {product['description']}"
            )

        lines.append("")

    remaining = len(products) - 5

    if remaining > 0:
        lines.append(
            f"Temos mais {remaining} opções que atendem "
            "aos seus critérios."
        )

    lines.append(
        "Quer saber mais sobre algum desses instrumentos? 🎸"
    )

    return "\n".join(lines)


# ==========================================================
# MUSIC STORE AGENT
# ==========================================================

class MusicStoreAgent:
    """Local agent with Ollama and deterministic catalog responses."""

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

    def _generate_response(self, messages, use_tools=True):
        """Request a response from the local LLM."""

        parameters = {
            "model": self.model,
            "messages": messages,
            "temperature": 0,
            "extra_body": {
                "think": False,
                "options": {"num_predict": 1024},
            },
        }

        if use_tools:
            parameters["tools"] = TOOLS
            parameters["tool_choice"] = "auto"

        return self.client.chat.completions.create(
            **parameters
        )

    def _retry_invalid_response(self, messages, answer):
        """Retry malformed output without new tool execution."""

        retry_messages = list(messages)

        retry_messages.extend([
            {
                "role": "assistant",
                "content": answer,
            },
            {
                "role": "user",
                "content": (
                    "Responda à pergunta original em português. "
                    "Utilize apenas os resultados das ferramentas. "
                    "Não use placeholders, JSON ou chamadas "
                    "de ferramentas como resposta."
                ),
            },
        ])

        response = self._generate_response(
            retry_messages,
            use_tools=False,
        )

        corrected = response.choices[0].message.content or ""

        if is_invalid_response(corrected):
            return (
                "Não consegui concluir a consulta com segurança. "
                "Pode reformular sua pergunta?"
            )

        return corrected

    # ======================================================
    # PRODUCT COMPARISON
    # ======================================================

    def _handle_product_comparison(self, user_message):
        """Handle recognized product comparisons deterministically."""

        request = parse_comparison_request(user_message)

        if request is None:
            return None

        product_a, product_b = request

        comparison = compare_products(product_a, product_b)

        if not comparison["success"]:
            return None

        answer = format_comparison(comparison)

        call_id = f"local_comparison_{len(self.messages)}"

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
                            "arguments": json.dumps(
                                {
                                    "product_a": product_a,
                                    "product_b": product_b,
                                },
                                ensure_ascii=False,
                            ),
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
    # MAIN CHAT
    # ======================================================

    def chat(self, user_message: str) -> str:
        """Handle conversation and tool execution."""

        if not user_message.strip():
            return "Por favor, escreva sua pergunta."

        comparison_answer = self._handle_product_comparison(
            user_message
        )

        if comparison_answer is not None:
            return comparison_answer

        # Work on a copy to avoid retaining failed turns.
        messages = list(self.messages)

        messages.append({
            "role": "user",
            "content": user_message,
        })

        for _ in range(5):

            response = self._generate_response(
                messages,
                use_tools=True,
            )

            assistant_message = response.choices[0].message

            # ----------------------------------------------
            # FINAL LLM RESPONSE
            # ----------------------------------------------

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

            # ----------------------------------------------
            # TOOL EXECUTION
            # ----------------------------------------------

            messages.append(
                assistant_message.model_dump(
                    exclude_none=True
                )
            )

            executed_tools = []

            for call in assistant_message.tool_calls:

                name = call.function.name
                arguments = {}

                try:
                    arguments = json.loads(
                        call.function.arguments
                    )

                    if not isinstance(arguments, dict):
                        raise ValueError(
                            "Arguments must be a JSON object"
                        )

                    result = execute_tool(name, arguments)

                except (ValueError, TypeError):
                    result = json.dumps({
                        "error": "Invalid tool arguments"
                    })

                # Store the result for deterministic handling.
                executed_tools.append((name, result))

                print(f"\n[Tool called: {name}]")

                if name in {
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
                    "tool_call_id": call.id,
                    "content": result,
                })

            # ----------------------------------------------
            # VERIFIED CATALOG RESPONSE
            # ----------------------------------------------

            # When the model requests only a product search,
            # generate the answer from the returned records.
            # This prevents hallucinated products and prices.

            if (
                len(executed_tools) == 1
                and executed_tools[0][0] == "search_products"
            ):
                try:
                    products = json.loads(
                        executed_tools[0][1]
                    )

                    if isinstance(products, list):
                        answer = format_catalog_response(products)

                        messages.append({
                            "role": "assistant",
                            "content": answer,
                        })

                        self.messages = messages
                        return answer

                except json.JSONDecodeError:
                    pass

        return (
            "Não consegui concluir a consulta. "
            "Por favor, tente reformular sua pergunta."
        )
