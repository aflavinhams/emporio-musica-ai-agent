
from decimal import Decimal, ROUND_HALF_UP

from src.tools.catalog import load_csv


def calculate_discount(price: Decimal, discount: Decimal) -> Decimal:
    """Calculate the promotional price using decimal precision."""
    return (
        price * (Decimal("1") - discount / Decimal("100"))
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def get_active_promotions() -> list[dict]:
    """Return active promotions for available products."""

    products = {
        int(row["product_id"]): row
        for row in load_csv("products.csv")
    }

    promotions = load_csv("promotions.csv")
    results = []

    for promotion in promotions:
        if promotion["is_active"] != "1":
            continue

        product_id = int(promotion["product_id"])
        product = products.get(product_id)

        if product is None:
            continue

        if (
            product["status"] != "active"
            or int(product["stock_quantity"]) <= 0
        ):
            continue

        original_price = Decimal(product["price_brl"])
        discount = Decimal(promotion["discount_percent"])

        if not Decimal("0") < discount < Decimal("100"):
            continue

        promotional_price = calculate_discount(
            original_price, discount
        )

        results.append({
            "promotion_id": int(promotion["promotion_id"]),
            "product_id": product_id,
            "product_name": product["name"],
            "description": promotion["description"],
            "original_price_brl": float(original_price),
            "discount_percent": float(discount),
            "promotional_price_brl": float(promotional_price),
            "stock_quantity": int(product["stock_quantity"]),
            "pix_discount_applicable": False,
        })

    return sorted(
        results,
        key=lambda item: item["promotional_price_brl"]
    )


def get_product_promotion(product_id: int) -> dict | None:
    """Find an active promotion for a specific product."""

    for promotion in get_active_promotions():
        if promotion["product_id"] == product_id:
            return promotion

    return None
