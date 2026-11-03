
import csv
import math
import re
import unicodedata
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parents[2] / "data"


# ==========================================================
# CSV LOADING
# ==========================================================

def load_csv(filename):
    """Load records from a CSV file in the project data directory."""

    path = Path(filename)

    if not path.is_absolute() and not path.exists():
        path = DATA_DIR / filename

    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


# ==========================================================
# TEXT NORMALIZATION
# ==========================================================

def normalize_text(value):
    """Normalize accents, case and whitespace."""

    text = unicodedata.normalize(
        "NFKD",
        str(value or "").casefold(),
    )

    text = "".join(
        character
        for character in text
        if not unicodedata.combining(character)
    )

    return re.sub(r"\s+", " ", text).strip()


def normalize_search_terms(value):
    """
    Normalize common Portuguese instrument names.

    Examples:
        guitarras elétricas -> guitarra
        guitarra elétrica  -> guitarra
        violões            -> violao
    """

    text = normalize_text(value)

    replacements = [
        (r"\bvioloes\b", "violao"),
        (r"\bviolao\b", "violao"),
        (r"\bguitarras\b", "guitarra"),
        (r"\bteclados\b", "teclado"),
        (r"\bpianos\b", "piano"),
        (r"\bbaixos\b", "baixo"),
        (r"\bukuleles\b", "ukulele"),
        (r"\bbaterias\b", "bateria"),
    ]

    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text)

    # The Guitarras category contains electric guitars.
    # Treat singular and plural variations consistently.
    if re.search(r"\bguitarra\b", text):
        text = re.sub(
            r"\b(eletrica|eletricas|eletrico|eletricos)\b",
            " ",
            text,
        )

    return re.sub(r"\s+", " ", text).strip()


# ==========================================================
# PRODUCT SEARCH MATCHING
# ==========================================================

def matches_search(product_name, category_name, query):
    """
    Match a query against product name and category.

    All meaningful query terms must match after normalization.
    """

    if not query or not str(query).strip():
        return True

    searchable = normalize_search_terms(
        f"{product_name} {category_name}"
    )

    normalized_query = normalize_search_terms(query)

    if not normalized_query:
        return True

    if normalized_query in searchable:
        return True

    ignored_words = {
        "a",
        "as",
        "o",
        "os",
        "de",
        "da",
        "das",
        "do",
        "dos",
        "em",
        "para",
        "por",
        "com",
        "um",
        "uma",
        "quero",
        "procurando",
        "voces",
        "vendem",
        "tem",
        "modelos",
        "modelo",
        "disponiveis",
    }

    query_words = [
        word
        for word in normalized_query.split()
        if word not in ignored_words
    ]

    if not query_words:
        return False

    searchable_words = set(searchable.split())

    return all(
        word in searchable_words
        for word in query_words
    )


# ==========================================================
# DATA CONVERSION
# ==========================================================

def _to_float(value, default=0.0):
    """Convert numeric CSV values to floats."""

    if value is None or str(value).strip() == "":
        return default

    try:
        return float(
            str(value).strip().replace(",", ".")
        )
    except (TypeError, ValueError):
        return default


def _to_int(value, default=0):
    """Convert numeric CSV values to integers."""

    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default


def _validate_max_price(max_price):
    """
    Validate a maximum price filter.

    Raises:
        ValueError: When the price is not numeric,
                    negative or non-finite.
    """

    if max_price is None:
        return None

    try:
        value = float(max_price)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "max_price must be a numeric value"
        ) from exc

    if not math.isfinite(value):
        raise ValueError(
            "max_price must be a finite number"
        )

    if value < 0:
        raise ValueError(
            "max_price cannot be negative"
        )

    return value


# ==========================================================
# CATEGORY MAPPING
# ==========================================================

def _category_mapping():
    """Map category IDs to names from categories.csv."""

    categories = load_csv("categories.csv")
    mapping = {}

    for category in categories:
        category_id = (
            category.get("category_id")
            or category.get("id")
        )

        category_name = (
            category.get("category_name")
            or category.get("name")
            or category.get("category")
        )

        if category_id is not None and category_name:
            mapping[
                str(category_id).strip()
            ] = category_name

    return mapping


# ==========================================================
# PRODUCT CATALOG SEARCH
# ==========================================================

def search_products(
    query="",
    max_price=None,
    category="",
    only_available=True,
):
    """
    Search musical instruments using verified catalog records.

    Args:
        query:
            Product name, model or instrument type.

        max_price:
            Optional non-negative maximum price in BRL.

        category:
            Optional category name.

        only_available:
            When True, include only active products
            with a positive stock quantity.

    Returns:
        A list of product dictionaries ordered by price.

    Raises:
        ValueError:
            If max_price is invalid or negative.
    """

    # Validate the price before executing the search.
    max_price = _validate_max_price(max_price)

    products = load_csv("products.csv")
    category_names = _category_mapping()

    results = []

    for product in products:
        product_id = (
            product.get("product_id")
            or product.get("id")
        )

        product_name = (
            product.get("name")
            or product.get("product_name")
            or ""
        )

        category_id = product.get("category_id")

        category_name = (
            category_names.get(
                str(category_id).strip(),
                "",
            )
            if category_id is not None
            else ""
        )

        if not category_name:
            category_name = (
                product.get("category_name")
                or product.get("category")
                or ""
            )

        price = _to_float(
            product.get(
                "price_brl",
                product.get("price"),
            )
        )

        stock = _to_int(
            product.get(
                "stock_quantity",
                product.get("stock", 0),
            )
        )

        status = str(
            product.get("status", "active")
        ).strip().casefold()

        description = (
            product.get("description")
            or ""
        )

        # ----------------------------------------------
        # AVAILABILITY FILTER
        # ----------------------------------------------

        if only_available:
            if stock <= 0:
                continue

            if status not in {
                "active",
                "available",
                "ativo",
                "disponivel",
            }:
                continue

        # ----------------------------------------------
        # PRICE FILTER
        # ----------------------------------------------

        if max_price is not None and price > max_price:
            continue

        # ----------------------------------------------
        # CATEGORY FILTER
        # ----------------------------------------------

        if category:
            requested_category = normalize_search_terms(
                category
            )

            current_category = normalize_search_terms(
                category_name
            )

            if (
                requested_category not in current_category
                and current_category not in requested_category
            ):
                continue

        # ----------------------------------------------
        # NAME AND QUERY MATCHING
        # ----------------------------------------------

        if not matches_search(
            product_name,
            category_name,
            query,
        ):
            continue

        results.append({
            "product_id": _to_int(product_id),
            "name": product_name,
            "category": category_name,
            "price_brl": price,
            "stock_quantity": stock,
            "status": product.get(
                "status",
                "active",
            ),
            "description": description,
        })

    # ----------------------------------------------
    # SORT BY PRICE AND NAME
    # ----------------------------------------------

    results.sort(
        key=lambda product: (
            product["price_brl"],
            normalize_text(product["name"]),
        )
    )

    return results
