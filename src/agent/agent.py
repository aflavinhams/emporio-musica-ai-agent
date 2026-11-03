
import inspect
import json
import os

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
            "Search the store's product catalog by product name, "
            "category, price and availability. "
            "Use this tool whenever customers ask about instruments, "
            "prices or stock. "
            "The query can contain a product name or category "
            "in Portuguese, such as 'violão' or 'guitarra'. "
            "For a budget of R$ 1000, use max_price=1000. "
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
                "description": "Return only available products.",
            },
        },
    ),

    tool_schema(
        "get_active_promotions",
        "Retrieve active promotions and discounted prices.",
        {},
    ),

    tool_schema(
        "get_product_promotion",
        "Retrieve an active promotion for a product ID.",
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
            "Retrieve order status after matching the order ID "
            "and the customer's registered email. "
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
            "Retrieve products from an order after checking "
            "the order ID and registered customer email."
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
            "Use this tool for questions about returns, "
            "refunds, exchanges, payments, shipping, "
            "warranties and opening hours. "
            "Returns relevant passages and page references."
        ),
        {
            "query": {
                "type": "string",
                "description": "Question about store policies.",
            },
            "top_k": {
                "type": "integer",
                "description": "Number of relevant passages.",
            },
        },
        ["query"],
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
        allowed_parameters = set(signature.parameters)

        filtered_arguments = {
            key: value
            for key, value in arguments.items()
            if key in allowed_parameters
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
# AI AGENT
# ==========================================================

class MusicStoreAgent:
    """Local conversational agent using Ollama and tool calling."""

    def __init__(self, client=None, model=None):

        self.client = client or OpenAI(
            base_url=os.getenv(
                "OLLAMA_BASE_URL",
                "http://localhost:11434/v1",
            ),
            api_key="ollama",
            timeout=120.0,
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

    def chat(self, user_message: str) -> str:
        """Process a user message and execute tool calls."""

        if not user_message.strip():
            return "Por favor, escreva sua pergunta."

        # Preserve the original history if a request fails.
        messages = list(self.messages)

        messages.append({
            "role": "user",
            "content": user_message,
        })

        max_iterations = 5

        for _ in range(max_iterations):

            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                temperature=0,
                extra_body={"think": False},
            )

            assistant_message = response.choices[0].message

            # --------------------------------------------------
            # FINAL RESPONSE
            # --------------------------------------------------

            if not assistant_message.tool_calls:

                answer = assistant_message.content or (
                    "Não consegui responder sua pergunta. "
                    "Pode tentar novamente?"
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

                # Development logs
                print(f"\n[Tool called: {tool_name}]")

                # Avoid printing customer emails or order details
                # when inspecting tool execution.
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

        # Do not persist incomplete conversations.
        return (
            "Não consegui concluir a consulta. "
            "Por favor, tente reformular sua pergunta."
        )
