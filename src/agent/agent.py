
import inspect
import json
import os
import re
import unicodedata
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
        "Retrieve active promotions from the provided dataset.",
        {},
    ),
    tool_schema(
        "get_product_promotion",
        "Retrieve a promotion using a numeric product ID.",
        {
            "product_id": {"type": "integer"},
        },
        ["product_id"],
    ),
    tool_schema(
        "get_order_status",
        (
            "Retrieve order status using order ID "
            "and registered customer email."
        ),
        {
            "order_id": {"type": "integer"},
            "customer_email": {"type": "string"},
        },
        ["order_id", "customer_email"],
    ),
    tool_schema(
        "get_order_items",
        (
            "Retrieve order items using order ID "
            "and registered customer email."
        ),
        {
            "order_id": {"type": "integer"},
            "customer_email": {"type": "string"},
        },
        ["order_id", "customer_email"],
    ),
    tool_schema(
        "search_policies",
        (
            "Search the store policy PDF for returns, refunds, "
            "payments, PIX, shipping, warranties, exchanges "
            "and opening hours."
        ),
        {
            "query": {"type": "string"},
            "top_k": {"type": "integer"},
        },
        ["query"],
    ),
    tool_schema(
        "compare_products",
        "Compare products using verified catalog specifications.",
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
# TEXT NORMALIZATION
# ==========================================================

def normalize_text(text: str) -> str:
    """Normalize text for Portuguese intent detection."""

    text = unicodedata.normalize(
        "NFKD",
        text.casefold(),
    )

    return "".join(
        character
        for character in text
        if not unicodedata.combining(character)
    )


# ==========================================================
# UNSUPPORTED OPERATIONS
# ==========================================================

UNSUPPORTED_ACTION_RESPONSE = (
    "Posso explicar as regras de devolução e reembolso, "
    "mas não consigo iniciar, aprovar ou processar "
    "esses procedimentos por aqui. "
    "Para solicitar uma devolução ou reembolso, "
    "entre em contato com a equipe de atendimento "
    "da Empório da Música. 😊"
)


def is_refund_action_request(message: str) -> bool:
    """Detect requests to execute unsupported operations."""

    text = normalize_text(message)

    operation = re.search(
        r"\b(devolu\w*|reembols\w*|estorn\w*)\b",
        text,
    )

    if not operation:
        return False

    direct_patterns = [
        r"\b(iniciar|abrir|processar|efetuar|realizar)\b",
        r"\b(quero|preciso|gostaria)\s+"
        r"(?:de\s+)?(?:solicitar|pedir|fazer)\b",
        r"\b(facam|processem|reembolsem)\b",
    ]

    if any(
        re.search(pattern, text)
        for pattern in direct_patterns
    ):
        return True

    capability = re.search(
        r"\b(voces|voce|podem|conseguem|pode|consegue)\b",
        text,
    )

    execution = re.search(
        r"\b(fazer|processar|iniciar|realizar|"
        r"efetuar|solicitar|aprovar)\b",
        text,
    )

    channel = re.search(
        r"\b(por aqui|diretamente|agora|neste chat|"
        r"nessa conversa)\b",
        text,
    )

    return bool(capability and execution and channel)


def has_unsupported_action_claim(answer: str) -> bool:
    """Detect positive claims of unavailable operations."""

    text = normalize_text(answer)

    limitations = [
        r"\bnao consigo\b",
        r"\bnao podemos\b",
        r"\bnao posso\b",
        r"\bnao e possivel\b",
        r"\bnao tenho como\b",
    ]

    if any(
        re.search(pattern, text)
        for pattern in limitations
    ):
        return False

    patterns = [
        r"\b(podemos|consigo|vou|vamos|iremos)\s+"
        r"(?:te\s+|lhe\s+)?"
        r"(?:ajudar a\s+)?"
        r"(?:iniciar|processar|efetuar|realizar|"
        r"aprovar|confirmar|finalizar)\s+"
        r"(?:a\s+|o\s+|sua\s+|seu\s+)?"
        r"(?:devolucao|reembolso|estorno|compra|pedido)",
        r"\b(?:envie|informe|passe)\b.{0,100}"
        r"\b(?:para|que)\s+"
        r"(?:iniciarmos|processarmos|realizarmos|"
        r"procedermos|aprovarmos)\b",
        r"\b(?:vamos|podemos)\s+"
        r"(?:dar inicio|prosseguir)\s+"
        r"(?:a|ao|com)\s+(?:devolucao|reembolso)",
    ]

    return any(
        re.search(pattern, text)
        for pattern in patterns
    )


# ==========================================================
# RETURN POLICY SAFEGUARDS
# ==========================================================

def return_receipt_state(message: str) -> str | None:
    """
    Identify return questions that mention purchase dates
    without specifying when the product was received.

    Returns:
        "unknown": purchase date given, receipt date missing
        "not_received": product explicitly not received
        None: no special handling required
    """

    text = normalize_text(message)

    return_topic = re.search(
        r"\b(devolu\w*|devolver|arrepend\w*|reembols\w*)\b",
        text,
    )

    purchase_time = re.search(
        r"\b(comprei|adquiri|fiz a compra)\b"
        r".{0,90}\b(ha\s+\d+\s+dias?|"
        r"ontem|anteontem|semana passada)\b",
        text,
    )

    if not return_topic or not purchase_time:
        return None

    not_received = re.search(
        r"\b(ainda nao recebi|nao recebi|"
        r"nao foi entregue)\b",
        text,
    )

    if not_received:
        return "not_received"

    receipt_info = re.search(
        r"\b(recebi|foi entregue|chegou)\b"
        r".{0,55}\b(ha\s+\d+\s+dias?|"
        r"ontem|anteontem|hoje)\b",
        text,
    )

    if receipt_info:
        return None

    return "unknown"


def format_return_clarification(state: str) -> str:
    """Avoid inferring receipt dates from purchase dates."""

    if state == "not_received":
        return (
            "Em compras online, o prazo de arrependimento "
            "previsto no manual é de 7 dias corridos após "
            "o recebimento do produto. Como você informou "
            "que ainda não recebeu o violão, não vou "
            "considerar a data da compra como início "
            "desse prazo. Para orientações sobre o seu caso, "
            "você também pode contatar a equipe da loja. 😊"
        )

    return (
        "Você pode solicitar a devolução de uma compra "
        "online em até 7 dias corridos após o recebimento "
        "do produto, conforme as políticas da loja. 😊\n\n"
        "O violão deve estar na embalagem original, "
        "sem sinais de uso e com todos os itens e manuais. "
        "O frete da devolução por arrependimento é pago "
        "pela loja, e o reembolso é feito pela mesma "
        "forma de pagamento original em até 10 dias úteis.\n\n"
        "Você informou quando fez a compra, mas ainda "
        "não quando recebeu o instrumento. "
        "Há quantos dias você recebeu o violão?"
    )


def has_return_policy_evidence(passages: list) -> bool:
    """Check whether retrieved passages support return rules."""

    text = normalize_text(
        " ".join(
            str(passage.get("content", ""))
            for passage in passages
            if isinstance(passage, dict)
        )
    )

    return bool(
        re.search(r"\b7\b", text)
        and "recebimento" in text
        and (
            "arrependimento" in text
            or "devolucao" in text
        )
    )


# ==========================================================
# RESPONSE VALIDATION
# ==========================================================

def is_invalid_response(response: str) -> bool:
    """Detect incomplete or unsupported responses."""

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
        r"\b(?:quer|deseja|posso|podemos|vamos)\b"
        r".{0,65}\b(?:confirmar|finalizar|processar)"
        r"\s+(?:a\s+|sua\s+)?compra\b",
    ]

    if any(
        re.search(
            pattern,
            response,
            re.IGNORECASE | re.DOTALL,
        )
        for pattern in invalid_patterns
    ):
        return True

    if has_unsupported_action_claim(response):
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
# POLICY ROUTING
# ==========================================================

POLICY_PATTERNS = [
    r"\bpix\b",
    r"\bpagament",
    r"\bparcel",
    r"\bfrete\b",
    r"\bentrega\b",
    r"\bdevolu",
    r"\bdevolver\b",
    r"\barrepend",
    r"\breembolso",
    r"\btroca\b",
    r"\btrocar\b",
    r"\bgarantia\b",
    r"\bhorario",
    r"\bfuncionamento\b",
]


def is_policy_question(message: str) -> bool:
    """Identify messages requiring policy retrieval."""

    text = normalize_text(message)

    if (
        re.search(r"\b(?:meu|meus)\s+pedid", text)
        or re.search(r"\b(?:rastrear|rastreamento)\b", text)
    ) and not re.search(
        r"\b(?:frete|prazo|politica|devolu|garantia)\b",
        text,
    ):
        return False

    return any(
        re.search(pattern, text)
        for pattern in POLICY_PATTERNS
    )


def build_policy_query(message: str) -> str:
    """
    Build an intent-focused policy retrieval query.

    Prefer policy-specific terms over long conversational
    questions to improve TF-IDF retrieval relevance.
    """

    text = normalize_text(message)

    # Returns and refunds take precedence over shipping.
    # This query was verified against the provided PDF:
    # it retrieves the return policy on page 4.
    if re.search(
        r"\b(devolu\w*|devolver|arrepend\w*|reembols\w*)\b",
        text,
    ):
        return (
            "devolução arrependimento 7 dias recebimento "
            "frete reembolso"
        )

    # PIX discounts cannot be combined with promotions.
    if re.search(r"\bpix\b", text):
        return (
            "Pagamento PIX desconto de 5% promoções "
            "não cumulativas"
        )

    # Warranty and product defect questions.
    if re.search(
        r"\b(garantia|defeito|troca)\b",
        text,
    ):
        return (
            "política trocas defeito garantia fabricante"
        )

    # Other policy questions retain the original text.
    return message


# ==========================================================
# VERIFIED CATALOG RESPONSE
# ==========================================================

def format_brl(value) -> str:
    """Format monetary values in Brazilian reais."""

    amount = Decimal(str(value))
    formatted = f"{amount:,.2f}"

    formatted = (
        formatted.replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )

    return f"R$ {formatted}"


def format_catalog_response(products: list[dict]) -> str:
    """Build catalog answers from verified product records."""

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
    """Local customer support agent using Ollama."""

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
        """Generate an LLM response through Ollama."""

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

    # ======================================================
    # RESPONSE RETRY
    # ======================================================

    def _retry_invalid_response(self, messages, answer):
        """Retry invalid answers without executing another tool."""

        retry_messages = list(messages)

        retry_messages.extend([
            {
                "role": "assistant",
                "content": answer,
            },
            {
                "role": "user",
                "content": (
                    "Corrija a resposta anterior em português. "
                    "Não use JSON ou placeholders. "
                    "Utilize somente dados verificados. "
                    "Não prometa iniciar ou processar compras, "
                    "devoluções, reembolsos ou pagamentos. "
                    "Não solicite dados para ações indisponíveis."
                ),
            },
        ])

        response = self._generate_response(
            retry_messages,
            use_tools=False,
        )

        corrected = (
            response.choices[0].message.content or ""
        )

        if is_invalid_response(corrected):
            return (
                "Não consegui apresentar essa informação "
                "com segurança. Recomendo entrar em contato "
                "com a equipe da loja."
            )

        return corrected

    # ======================================================
    # HISTORY HELPERS
    # ======================================================

    def _record_local_tool(
        self,
        messages,
        name,
        arguments,
        result,
    ):
        """Record executed tools in the conversation history."""

        call_id = f"local_{name}_{len(messages)}"

        messages.extend([
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": call_id,
                        "type": "function",
                        "function": {
                            "name": name,
                            "arguments": json.dumps(
                                arguments,
                                ensure_ascii=False,
                            ),
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": call_id,
                "content": result,
            },
        ])

    # ======================================================
    # POLICY RETRIEVAL
    # ======================================================

    def _retrieve_required_policy(
        self,
        messages,
        user_message,
    ):
        """Retrieve relevant policy evidence before generation."""

        arguments = {
            "query": build_policy_query(user_message),
            "top_k": 3,
        }

        result = execute_tool(
            "search_policies",
            arguments,
        )

        print("\n[Tool called: search_policies]")
        print(f"[Arguments: {arguments}]")

        try:
            passages = json.loads(result)
        except json.JSONDecodeError:
            passages = None

        if not isinstance(passages, list) or not passages:
            print("[Policy retrieval: no usable evidence]")
            return []

        self._record_local_tool(
            messages,
            "search_policies",
            arguments,
            result,
        )

        print(
            f"[Policy passages retrieved: {len(passages)}]"
        )

        return passages

    # ======================================================
    # DETERMINISTIC PRODUCT COMPARISON
    # ======================================================

    def _handle_product_comparison(self, user_message):
        """Compare named products using verified catalog data."""

        request = parse_comparison_request(user_message)

        if request is None:
            return None

        product_a, product_b = request
        comparison = compare_products(
            product_a,
            product_b,
        )

        if not comparison["success"]:
            return None

        answer = format_comparison(comparison)

        messages = list(self.messages)

        messages.append({
            "role": "user",
            "content": user_message,
        })

        self._record_local_tool(
            messages,
            "compare_products",
            {
                "product_a": product_a,
                "product_b": product_b,
            },
            json.dumps(
                comparison,
                ensure_ascii=False,
                default=str,
            ),
        )

        messages.append({
            "role": "assistant",
            "content": answer,
        })

        self.messages = messages

        print("\n[Tool called: compare_products]")
        print("[Comparison based on catalog specifications]")

        return answer

    # ======================================================
    # UNSUPPORTED ACTION BLOCK
    # ======================================================

    def _handle_unsupported_action(self, user_message):
        """Block unavailable return and refund operations."""

        if not is_refund_action_request(user_message):
            return None

        answer = UNSUPPORTED_ACTION_RESPONSE

        self.messages.extend([
            {
                "role": "user",
                "content": user_message,
            },
            {
                "role": "assistant",
                "content": answer,
            },
        ])

        print(
            "\n[Safety rule: unsupported operation blocked]"
        )

        return answer

    # ======================================================
    # MAIN CHAT
    # ======================================================

    def chat(self, user_message: str) -> str:
        """Process a customer message and execute tools."""

        if not user_message.strip():
            return "Por favor, escreva sua pergunta."

        # Block unavailable transactional operations.
        unsupported_answer = self._handle_unsupported_action(
            user_message
        )

        if unsupported_answer is not None:
            return unsupported_answer

        # Handle recognized comparisons deterministically.
        comparison_answer = self._handle_product_comparison(
            user_message
        )

        if comparison_answer is not None:
            return comparison_answer

        messages = list(self.messages)

        messages.append({
            "role": "user",
            "content": user_message,
        })

        receipt_state = return_receipt_state(
            user_message
        )

        # Mandatory policy retrieval.
        if is_policy_question(user_message):

            passages = self._retrieve_required_policy(
                messages,
                user_message,
            )

            if not passages:
                answer = (
                    "Não consegui consultar as políticas da loja "
                    "para confirmar essa informação. "
                    "Recomendo entrar em contato com a equipe "
                    "de atendimento."
                )

                messages.append({
                    "role": "assistant",
                    "content": answer,
                })

                self.messages = messages
                return answer

            # Keep purchase and receipt dates separate.
            if receipt_state is not None:

                if not has_return_policy_evidence(passages):
                    answer = (
                        "Não consegui recuperar informações "
                        "suficientes sobre o prazo de devolução. "
                        "Recomendo consultar a equipe da loja."
                    )
                else:
                    answer = format_return_clarification(
                        receipt_state
                    )

                messages.append({
                    "role": "assistant",
                    "content": answer,
                })

                self.messages = messages

                print(
                    "[Safety rule: purchase and receipt "
                    "dates kept separate]"
                )

                return answer

        # Continue with normal LLM and tool-calling flow.
        for _ in range(5):

            response = self._generate_response(
                messages,
                use_tools=True,
            )

            assistant_message = (
                response.choices[0].message
            )

            # ----------------------------------------------
            # FINAL RESPONSE
            # ----------------------------------------------

            if not assistant_message.tool_calls:

                answer = (
                    assistant_message.content or ""
                )

                if is_invalid_response(answer):
                    answer = self._retry_invalid_response(
                        messages,
                        answer,
                    )

                if is_invalid_response(answer):
                    answer = (
                        "Não consegui responder com segurança. "
                        "Recomendo entrar em contato com "
                        "a equipe de atendimento da loja."
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

                    result = execute_tool(
                        name,
                        arguments,
                    )

                except (ValueError, TypeError):
                    result = json.dumps({
                        "error": "Invalid tool arguments"
                    })

                executed_tools.append(
                    (name, result)
                )

                print(f"\n[Tool called: {name}]")

                if name in {
                    "get_order_status",
                    "get_order_items",
                }:
                    print("[Arguments: redacted]")
                    print("[Tool result: redacted]")
                else:
                    print(f"[Arguments: {arguments}]")
                    print(
                        f"[Tool result: {result[:3000]}]"
                    )

                messages.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": result,
                })

            # ----------------------------------------------
            # VERIFIED CATALOG RESPONSE
            # ----------------------------------------------

            if (
                len(executed_tools) == 1
                and executed_tools[0][0] == "search_products"
            ):
                try:
                    products = json.loads(
                        executed_tools[0][1]
                    )

                    if isinstance(products, list):

                        answer = format_catalog_response(
                            products
                        )

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
