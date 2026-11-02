
import csv
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def load_csv(filename: str) -> list[dict]:
    """Load records from a CSV file."""
    file_path = DATA_DIR / filename

    with open(file_path, "r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


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

        if query.casefold() not in name.casefold():
            continue

        if category and category.casefold() not in category_name.casefold():
            continue

        if max_price is not None and price > max_price:
            continue

        if only_available and (status != "active" or stock <= 0):
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
