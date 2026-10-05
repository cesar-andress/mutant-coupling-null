"""Bug-level bootstrap (percentile)."""

from __future__ import annotations

import random
from typing import List, Sequence, Tuple


def percentile_ci(
    values: Sequence[float],
    n_resamples: int = 10000,
    seed: int = 20261005,
    alpha: float = 0.05,
) -> Tuple[float, float, float, List[float]]:
    vals = list(values)
    n = len(vals)
    if n == 0:
        raise ValueError("empty sample")
    mean = sum(vals) / n
    rng = random.Random(seed)
    dist = []
    for _ in range(n_resamples):
        draw = [vals[rng.randrange(n)] for _ in range(n)]
        dist.append(sum(draw) / n)
    dist.sort()
    lo_i = int(alpha / 2 * n_resamples)
    hi_i = min(n_resamples - 1, int((1 - alpha / 2) * n_resamples))
    return mean, dist[lo_i], dist[hi_i], dist
