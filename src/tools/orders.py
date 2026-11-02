
import hmac

from src.tools.catalog import load_csv


def _find_authorized_order(
    order_id: int,
    customer_email: str
) -> dict | None:
    """Match an order with its customer's registered email."""

    if order_id <= 0 or not customer_email.strip():
        return None

    orders = load_csv("orders.csv")
    customers = load_csv("customers.csv")

    order = next(
        (
            row for row in orders
            if int(row["order_id"]) == order_id
        ),
        None
    )

    if order is None:
        return None

    customer = next(
        (
            row for row in customers
            if row["customer_id"] == order["customer_id"]
        ),
        None
    )

    if customer is None:
        return None

    registered_email = customer["email"].strip().casefold()
    provided_email = customer_email.strip().casefold()

    if not hmac.compare_digest(
        registered_email.encode(),
        provided_email.encode()
    ):
        return None

    return order


def get_order_status(
    order_id: int,
    customer_email: str
) -> dict:
    """Retrieve order status after basic customer data matching."""

    order = _find_authorized_order(
        order_id, customer_email
    )

    if order is None:
        return {
            "success": False,
            "message": (
                "Unable to verify this order. "
                "Please check the order number and email."
            )
        }

    return {
        "success": True,
        "order_id": int(order["order_id"]),
        "order_date": order["order_date"],
        "status": order["status"],
        "total_brl": float(order["total_brl"]),
        "payment_method": order["payment_method"],
        "tracking_code": order["tracking_code"] or None,
        "estimated_delivery": (
            order["estimated_delivery"] or None
        ),
    }


def get_order_items(
    order_id: int,
    customer_email: str
) -> dict:
    """Retrieve products in an order after customer data matching."""

    order = _find_authorized_order(
        order_id, customer_email
    )

    if order is None:
        return {
            "success": False,
            "message": (
                "Unable to verify this order. "
                "Please check the order number and email."
            )
        }

    order_items = load_csv("order_items.csv")
    products = {
        int(row["product_id"]): row
        for row in load_csv("products.csv")
    }

    items = []

    for item in order_items:
        if int(item["order_id"]) != order_id:
            continue

        product_id = int(item["product_id"])
        product = products.get(product_id)

        items.append({
            "product_id": product_id,
            "product_name": (
                product["name"] if product else "Unknown product"
            ),
            "quantity": int(item["quantity"]),
        })

    return {
        "success": True,
        "order_id": order_id,
        "items": items,
    }
