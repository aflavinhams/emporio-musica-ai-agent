
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


TOOL_FUNCTIONS = {
    "search_products": search_products,
    "get_active_promotions": get_active_promotions,
    "get_product_promotion": get_product_promotion,
    "get_order_status": get_order_status,
    "get_order_items": get_order_items,
    "search_policies": search_policies,
}


def tool_schema(name, description, properties, required=None):
    """Build a function calling definition."""

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
        "Search products by name, category, price or stock availability.",
        {
            "query": {"type": "string"},
            "category": {"type": "string"},
            "max_price": {"type": "number"},
            "only_available": {"type": "boolean"},
        },
    ),
    tool_schema(
        "get_active_promotions",
        "Retrieve active product promotions and discounted prices.",
        {},
    ),
    tool_schema(
        "get_product_promotion",
        "Retrieve a promotion for a specific product ID.",
        {
            "product_id": {"type": "integer"},
        },
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
        "Retrieve products from an order after customer verification.",
        {
            "order_id": {"type": "integer"},
            "customer_email": {"type": "string"},
        },
        ["order_id", "customer_email"],
    ),
    tool_schema(
        "search_policies",
        "Search the store policy manual for relevant passages.",
        {
            "query": {"type": "string"},
            "top_k": {"type": "integer"},
        },
        ["query"],
    ),
]


def execute_tool(name: str, arguments: dict) -> str:
    """Execute an allowed tool and serialize its result."""

    function = TOOL_FUNCTIONS.get(name)

    if function is None:
        return json.dumps({
            "error": "Unknown tool"
        })

    if not isinstance(arguments, dict):
        return json.dumps({
            "error": "Invalid tool arguments"
        })

    # Remove unknown arguments and rely on the Python
    # function signature for required arguments.
    import inspect

    signature = inspect.signature(function)
    allowed = set(signature.parameters)

    arguments = {
        key: value
        for key, value in arguments.items()
        if key in allowed
    }

    try:
        result = function(**arguments)

        return json.dumps(
            result,
            ensure_ascii=False,
            default=str
        )

    except (TypeError, ValueError, FileNotFoundError):
        return json.dumps({
            "error": "Tool execution failed",
            "message": "Please check the supplied parameters."
        })


class MusicStoreAgent:
    """Local LLM agent with tool calling and session history."""

    def __init__(self, client=None, model=None):
        self.client = client or OpenAI(
            base_url=os.getenv(
                "OLLAMA_BASE_URL",
                "http://localhost:11434/v1"
            ),
            api_key="ollama",
            timeout=120.0,
        )

        self.model = model or os.getenv(
            "OLLAMA_MODEL", "qwen3:4b"
        )

        self.messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            }
        ]

    def chat(self, user_message: str) -> str:
        """Process a message and execute tool calls."""

        if not user_message.strip():
            return "Por favor, escreva sua pergunta."

        messages = list(self.messages)

        messages.append({
            "role": "user",
            "content": user_message
        })

        for _ in range(5):
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=TOOLS,
                temperature=0,
            )

            assistant_message = response.choices[0].message

            if not assistant_message.tool_calls:
                answer = assistant_message.content or (
                    "Não consegui responder sua pergunta. "
                    "Pode tentar novamente?"
                )

                messages.append({
                    "role": "assistant",
                    "content": answer
                })

                self.messages = messages
                return answer

            messages.append(
                assistant_message.model_dump(
                    exclude_none=True
                )
            )

            for tool_call in assistant_message.tool_calls:
                tool_name = tool_call.function.name

                try:
                    arguments = json.loads(
                        tool_call.function.arguments
                    )
                    result = execute_tool(
                        tool_name,
                        arguments
                    )
                except (ValueError, TypeError):
                    result = json.dumps({
                        "error": "Invalid tool arguments"
                    })

                print(f"[Tool called: {tool_name}]")
                
                print(f"[Arguments: {arguments}]")
                print(f"[Tool result: {result[:3000]}]")

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result
                })

        return (
            "Não consegui concluir a consulta. "
            "Por favor, tente reformular sua pergunta."
        )
