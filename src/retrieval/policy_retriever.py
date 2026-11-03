
import re
from functools import lru_cache
from pathlib import Path

from pypdf import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


POLICY_PATH = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "politicas_da_loja.pdf"
)


def split_text(
    text: str,
    chunk_size: int = 900,
    overlap: int = 150
) -> list[str]:
    """Split text into overlapping chunks."""

    if not 0 <= overlap < chunk_size:
        raise ValueError(
            "overlap must be smaller than chunk_size"
        )

    chunks = []
    start = 0

    while start < len(text):
        end = min(start + chunk_size, len(text))

        if end < len(text):
            split_at = text.rfind(
                " ",
                start + chunk_size // 2,
                end
            )

            if split_at > start:
                end = split_at

        chunks.append(text[start:end].strip())

        if end == len(text):
            break

        start = max(start + 1, end - overlap)

    return chunks


@lru_cache(maxsize=1)
def _build_index():
    """Extract and index policy document passages."""

    if not POLICY_PATH.exists():
        raise FileNotFoundError(
            f"Policy file not found: {POLICY_PATH}"
        )

    reader = PdfReader(str(POLICY_PATH))
    passages = []

    for page_number, page in enumerate(
        reader.pages, start=1
    ):
        text = re.sub(
            r"\s+",
            " ",
            page.extract_text() or ""
        ).strip()

        if not text:
            continue

        for chunk in split_text(text):
            passages.append({
                "page": page_number,
                "content": chunk
            })

    if not passages:
        raise ValueError(
            "No searchable text found in the policy PDF"
        )

    vectorizer = TfidfVectorizer(
        strip_accents="unicode",
        ngram_range=(1, 2)
    )

    matrix = vectorizer.fit_transform(
        passage["content"] for passage in passages
    )

    return passages, vectorizer, matrix


def search_policies(
    query: str,
    top_k: int = 3,
    min_score: float = 0.08
) -> list[dict]:
    """Retrieve relevant policy passages with page references."""

    if not query.strip():
        return []

    if top_k < 1:
        raise ValueError("top_k must be at least 1")

    passages, vectorizer, matrix = _build_index()

    query_vector = vectorizer.transform([query])

    scores = cosine_similarity(
        query_vector, matrix
    ).ravel()

    ranked_indices = scores.argsort()[::-1]

    return [
        {
            "page": passages[index]["page"],
            "content": passages[index]["content"],
            "score": round(float(scores[index]), 4)
        }
        for index in ranked_indices[:top_k]
        if scores[index] >= min_score
    ]
