from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable


def expected_score(ra: float, rb: float) -> float:
    return 1.0 / (1.0 + 10.0 ** ((rb - ra) / 400.0))


def compute_elo(
    matches: Iterable[dict],
    base_rating: float = 1500.0,
    k_factor: float = 20.0,
) -> Dict[str, float]:
    ratings: Dict[str, float] = defaultdict(lambda: base_rating)
    for m in matches:
        a = str(m["a"])
        b = str(m["b"])
        sa = float(m["score_a"])
        ra = ratings[a]
        rb = ratings[b]
        ea = expected_score(ra, rb)
        delta = k_factor * (sa - ea)
        ratings[a] = ra + delta
        ratings[b] = rb - delta
    return dict(ratings)

