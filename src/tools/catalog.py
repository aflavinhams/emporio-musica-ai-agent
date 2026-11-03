
import csv
from pathlib import Path
import re
import unicodedata

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def load_csv(filename: str) -> list[dict]:
    """Load records from a CSV file."""
    file_path = DATA_DIR / filename

    with open(file_path, "r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))

def normalize_text(text: str) -> str:
    """Normalize text for accent-insensitive product search."""
    text = unicodedata.normalize("NFKD", text.casefold())
    text = "".join(
        char for char in text
        if not unicodedata.combining(char)
    )
    return re.sub(r"\s+", " ", text).strip()


def matches_search(term: str, text: str) -> bool:
    """Match terms while handling common Portuguese plurals."""
    term = normalize_text(term)
    text = normalize_text(text)

    if term in text:
        return True

    # Handle common singular/plural forms such as violão/violões.
    variants = {
        "violao": "violoes",
        "violoes": "violao",
    }

    alternative = variants.get(term)
    return alternative is not None and alternative in text


def search_products(
    query: str = "",
    max_price: float | None = None,
    category: str = "",
    only_available: bool = True
) -> list[dict]:
    """Search products by name, category, price and availability."""

    if max_price is not None and max_price < 0:
        raise ValueError("max_price must be non-negative")

    categories = {
        row["category_id"]: row["name"]
        for row in load_csv("categories.csv")
    }

    products = load_csv("products.csv")
    results = []

    for product in products:
        name = product["name"]
        price = float(product["price_brl"])
        stock = int(product["stock_quantity"])
        status = product["status"]

        category_name = categories.get(
            product["category_id"], "Unknown"
        )

        # Search by product name or category
        if query.strip():
            matches_name = matches_search(query, name)
            matches_category = matches_search(
                query, category_name
            )

            if not (matches_name or matches_category):
                continue

        # Filter by category
        if category.strip() and not matches_search(
            category, category_name
        ):
            continue

        # Filter by maximum price
        if max_price is not None and price > max_price:
            continue

        # Filter by stock availability
        if only_available and (
            status != "active" or stock <= 0
        ):
            continue

        results.append({
            "product_id": int(product["product_id"]),
            "name": name,
            "category": category_name,
            "price_brl": price,
            "stock_quantity": stock,
            "status": status,
            "description": product["description"],
        })

    return sorted(
        results,
        key=lambda product: (
            product["price_brl"],
            product["name"]
        )
    )
