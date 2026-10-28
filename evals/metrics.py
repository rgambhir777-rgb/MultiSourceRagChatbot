"""Retrieval metrics. Pure functions: no models or databases, so they are easy to test.

`ranks` holds, for each question, the 1-based position of the first correct chunk in the
results, or None if no correct chunk was returned at all.
"""

from collections.abc import Sequence


def hit_at_k(ranks: Sequence[int | None], k: int) -> float:
    """Share of questions whose correct chunk appears in the top k (0.0 to 1.0)."""
    if not ranks:
        return 0.0
    return sum(1 for rank in ranks if rank is not None and rank <= k) / len(ranks)


def mean_reciprocal_rank(ranks: Sequence[int | None]) -> float:
    """Average of 1/rank (rank 1 → 1.0, rank 2 → 0.5, not found → 0). Rewards correct
    chunks that appear near the top, not just somewhere in the list."""
    if not ranks:
        return 0.0
    return sum(1 / rank for rank in ranks if rank is not None) / len(ranks)


def first_correct_rank(
    results: Sequence[tuple[str, str]], expected_source: str, expected_phrase: str
) -> int | None:
    """1-based rank of the first (source, text) result that is the expected chunk."""
    for rank, (source, text) in enumerate(results, start=1):
        if source == expected_source and expected_phrase.lower() in text.lower():
            return rank
    return None
