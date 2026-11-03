
import json
import re
import unicodedata
from decimal import Decimal

from src.tools.catalog import load_csv


SPEC_LABELS = {
    "top": "Madeira do tampo",
    "back_sides": "Fundo e laterais",
    "neck": "Braço",
    "strings": "Cordas",
    "scale": "Escala",
    "electronics": "Eletrônica",
    "color": "Cor",
}


def normalize(text: str) -> str:
    """Normalize product names for matching."""
    text = unicodedata.normalize("NFKD", text.casefold())
    text = "".join(
        char for char in text
        if not unicodedata.combining(char)
    )
    return re.sub(r"\s+", " ", text).strip()


def find_product(name: str) -> dict | None:
    """Find a product by its name or a unique partial name."""
    term = normalize(name)

    if not term:
        return None

    products = load_csv("products.csv")

    matches = [
        product
        for product in products
        if term in normalize(product["name"])
    ]

    if len(matches) != 1:
        return None

    return matches[0]


def format_brl(value: str | Decimal) -> str:
    """Format a monetary amount in Brazilian reais."""
    amount = Decimal(str(value))

    formatted = f"{amount:,.2f}"
    formatted = formatted.replace(",", "X")
    formatted = formatted.replace(".", ",")
    formatted = formatted.replace("X", ".")

    return f"R$ {formatted}"


def compare_products(
    product_a: str,
    product_b: str,
) -> dict:
    """Compare two products using verified catalog attributes."""

    first = find_product(product_a)
    second = find_product(product_b)

    if first is None or second is None:
        return {
            "success": False,
            "message": (
                "Não consegui identificar os dois modelos "
                "com segurança. Informe os nomes completos."
            ),
        }

    if first["product_id"] == second["product_id"]:
        return {
            "success": False,
            "message": "Informe dois modelos diferentes.",
        }

    first_specs = json.loads(first.get("specs") or "{}")
    second_specs = json.loads(second.get("specs") or "{}")

    def summarize(product, specs):
        return {
            "name": product["name"],
            "price_brl": product["price_brl"],
            "stock_quantity": int(product["stock_quantity"]),
            "available": (
                product["status"] == "active"
                and int(product["stock_quantity"]) > 0
            ),
            "description": product["description"],
            "specifications": specs,
        }

    return {
        "success": True,
        "first": summarize(first, first_specs),
        "second": summarize(second, second_specs),
        "price_difference_brl": float(
            abs(
                Decimal(first["price_brl"])
                - Decimal(second["price_brl"])
            )
        ),
    }


def format_comparison(result: dict) -> str:
    """Build a factual customer-facing comparison."""

    if not result["success"]:
        return result["message"]

    first = result["first"]
    second = result["second"]

    lines = ["Claro! Veja a comparação dos dois modelos:", ""]

    for product in (first, second):
        lines.append(product["name"])
        lines.append(
            f"Preço: {format_brl(product['price_brl'])}"
        )

        availability = (
            f"{product['stock_quantity']} unidades"
            if product["available"]
            else "Indisponível"
        )
        lines.append(f"Estoque: {availability}")

        for field, label in SPEC_LABELS.items():
            value = product["specifications"].get(field)
            if value is not None and str(value).strip():
                if field == "electronics":
                    value = {
                        "yes": "Sim",
                        "no": "Não",
                    }.get(str(value).lower(), value)

                lines.append(f"{label}: {value}")

        lines.append(f"Descrição: {product['description']}")
        lines.append("")

    price_a = Decimal(first["price_brl"])
    price_b = Decimal(second["price_brl"])

    if price_a < price_b:
        cheaper = first
    elif price_b < price_a:
        cheaper = second
    else:
        cheaper = None

    lines.append(
        "Diferença de preço: "
        + format_brl(result["price_difference_brl"])
    )

    if cheaper is not None and cheaper["available"]:
        lines.append(
            f"Se sua prioridade é economizar, "
            f"o {cheaper['name']} custa menos."
        )

    lines.append(
        "Não é possível afirmar qual possui qualidade "
        "sonora superior apenas com esses dados."
    )

    return "\n".join(lines)


def parse_comparison_request(message: str):
    """Recognize explicit requests comparing two named products."""

    patterns = [
        r"\bentre\s+(?:o\s+|a\s+)?(.+?)\s+e\s+"
        r"(?:o\s+|a\s+)?(.+?)(?:[?!.]|$)",
        r"\bcompar(?:e|ar)\s+(.+?)\s+com\s+"
        r"(.+?)(?:[?!.]|$)",
    ]

    for pattern in patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            first = match.group(1).strip()
            second = match.group(2).strip()
            if first and second:
                return first, second

    return None
