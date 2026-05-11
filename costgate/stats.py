from __future__ import annotations

import math
from typing import Dict, List

import numpy as np


def _norm_cdf(z: float) -> float:
    # Standard normal CDF via erf
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def _rankdata(a: np.ndarray) -> np.ndarray:
    """
    Average ranks for ties, like scipy.stats.rankdata(method='average').
    """
    order = np.argsort(a, kind="mergesort")
    ranks = np.empty(len(a), dtype=float)

    i = 0
    while i < len(a):
        j = i
        while j + 1 < len(a) and a[order[j + 1]] == a[order[i]]:
            j += 1
        avg_rank = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg_rank
        i = j + 1
    return ranks


def mann_whitney_u_greater(x: List[float], y: List[float]) -> Dict[str, float]:
    """
    Mann–Whitney U test, one-sided alternative: x > y (PR worse).
    Uses normal approximation with tie correction.
    Returns: U, z, p_value
    """
    x = [float(v) for v in x if math.isfinite(float(v))]
    y = [float(v) for v in y if math.isfinite(float(v))]
    if len(x) == 0 or len(y) == 0:
        return {"u": float("nan"), "z": float("nan"), "p_value": float("nan")}

    a = np.array(x + y, dtype=float)
    ranks = _rankdata(a)

    n1 = len(x)
    n2 = len(y)

    r1 = float(np.sum(ranks[:n1]))
    u1 = r1 - n1 * (n1 + 1) / 2.0

    mu = n1 * n2 / 2.0

    # tie correction
    _, counts = np.unique(a, return_counts=True)
    tie_term = float(np.sum(counts**3 - counts))
    n = n1 + n2
    sigma2 = (n1 * n2 / 12.0) * ((n + 1) - tie_term / (n * (n - 1)) if n > 1 else 0.0)
    sigma = math.sqrt(max(sigma2, 1e-12))

    # continuity correction for "greater"
    z = (u1 - mu - 0.5) / sigma
    p = 1.0 - _norm_cdf(z)
    p = min(max(p, 0.0), 1.0)
    return {"u": float(u1), "z": float(z), "p_value": float(p)}


def bootstrap_ci_mean_diff(
    baseline: List[float],
    pr: List[float],
    alpha: float = 0.05,
    n_boot: int = 8000,
    seed: int = 0,
) -> Dict[str, float]:
    """
    Bootstrap percentile CI for mean(pr) - mean(baseline).
    """
    b = np.array([float(v) for v in baseline if math.isfinite(float(v))], dtype=float)
    p = np.array([float(v) for v in pr if math.isfinite(float(v))], dtype=float)
    if len(b) == 0 or len(p) == 0:
        return {
            "mean_diff": float("nan"),
            "ci_low": float("nan"),
            "ci_high": float("nan"),
        }

    rng = np.random.default_rng(seed)
    diffs = np.empty(n_boot, dtype=float)

    for i in range(n_boot):
        bs = rng.choice(b, size=len(b), replace=True)
        ps = rng.choice(p, size=len(p), replace=True)
        diffs[i] = float(np.mean(ps) - np.mean(bs))

    mean_diff = float(np.mean(p) - np.mean(b))
    lo = float(np.percentile(diffs, 100.0 * (alpha / 2.0)))
    hi = float(np.percentile(diffs, 100.0 * (1.0 - alpha / 2.0)))
    return {"mean_diff": mean_diff, "ci_low": lo, "ci_high": hi}


def cliffs_delta(baseline: List[float], pr: List[float]) -> float:
    """
    Cliff's delta for PR vs baseline: + means PR tends larger (worse for gated metrics).
    """
    b = [float(v) for v in baseline if math.isfinite(float(v))]
    p = [float(v) for v in pr if math.isfinite(float(v))]
    if not b or not p:
        return float("nan")

    gt = 0
    lt = 0
    for pv in p:
        for bv in b:
            if pv > bv:
                gt += 1
            elif pv < bv:
                lt += 1
    n = len(b) * len(p)
    return (gt - lt) / n if n else float("nan")


def bootstrap_ci_cliffs_delta(
    baseline: List[float],
    pr: List[float],
    alpha: float = 0.05,
    n_boot: int = 8000,
    seed: int = 1,
) -> Dict[str, float]:
    b = np.array([float(v) for v in baseline if math.isfinite(float(v))], dtype=float)
    p = np.array([float(v) for v in pr if math.isfinite(float(v))], dtype=float)
    if len(b) == 0 or len(p) == 0:
        return {"delta": float("nan"), "ci_low": float("nan"), "ci_high": float("nan")}

    rng = np.random.default_rng(seed)
    deltas = np.empty(n_boot, dtype=float)
    for i in range(n_boot):
        bs = rng.choice(b, size=len(b), replace=True).tolist()
        ps = rng.choice(p, size=len(p), replace=True).tolist()
        deltas[i] = cliffs_delta(bs, ps)

    d = cliffs_delta(b.tolist(), p.tolist())
    lo = float(np.percentile(deltas, 100.0 * (alpha / 2.0)))
    hi = float(np.percentile(deltas, 100.0 * (1.0 - alpha / 2.0)))
    return {"delta": float(d), "ci_low": lo, "ci_high": hi}
