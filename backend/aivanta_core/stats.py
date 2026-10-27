"""Small, dependency-free statistics used for evidence assessment.

Only what the product needs: means, sample standard deviations, Welch's
two-sample interval for a difference in means, and a Wald interval for a
difference in proportions. All intervals are two-sided 95 %.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Sequence

# Two-sided 95 % critical values of Student's t by degrees of freedom.
_T95 = {
    1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365,
    8: 2.306, 9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145,
    15: 2.131, 16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086, 21: 2.080,
    22: 2.074, 23: 2.069, 24: 2.064, 25: 2.060, 26: 2.056, 27: 2.052, 28: 2.048,
    29: 2.045, 30: 2.042, 40: 2.021, 60: 2.000, 120: 1.980,
}
Z95 = 1.959964


def t_critical_95(df: float) -> float:
    if df <= 0 or math.isnan(df):
        raise ValueError("degrees of freedom must be positive")
    if df >= 1000:
        return Z95
    keys = sorted(_T95)
    if df <= 1:
        return _T95[1]
    for lo, hi in zip(keys, keys[1:], strict=False):
        if lo <= df <= hi:
            if df == lo:
                return _T95[lo]
            # linear interpolation in 1/df, which is close to exact for t quantiles
            w = (1 / lo - 1 / df) / (1 / lo - 1 / hi)
            return _T95[lo] + w * (_T95[hi] - _T95[lo])
    # between 120 and 1000
    w = (1 / 120 - 1 / df) / (1 / 120 - 1 / 1000)
    return _T95[120] + w * (Z95 - _T95[120])


def mean(values: Sequence[float]) -> Optional[float]:
    return sum(values) / len(values) if values else None


def sample_std(values: Sequence[float]) -> Optional[float]:
    n = len(values)
    if n < 2:
        return None
    m = sum(values) / n
    return math.sqrt(sum((v - m) ** 2 for v in values) / (n - 1))


@dataclass(frozen=True)
class Interval:
    estimate: float
    low: float
    high: float

    @property
    def excludes_zero(self) -> bool:
        return self.low > 0 or self.high < 0


def welch_difference(a: Sequence[float], b: Sequence[float]) -> Optional[Interval]:
    """95 % interval for mean(a) - mean(b). ``None`` if either group has n < 2."""
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return None
    ma, mb = sum(a) / na, sum(b) / nb
    va, vb = sample_std(a) ** 2, sample_std(b) ** 2  # type: ignore[operator]
    se2 = va / na + vb / nb
    diff = ma - mb
    if se2 == 0:
        return Interval(diff, diff, diff)
    df = se2**2 / ((va / na) ** 2 / (na - 1) + (vb / nb) ** 2 / (nb - 1))
    half = t_critical_95(df) * math.sqrt(se2)
    return Interval(diff, diff - half, diff + half)


def proportion_difference(
    successes_a: int, n_a: int, successes_b: int, n_b: int
) -> Optional[Interval]:
    """95 % Wald interval for p_a - p_b. ``None`` if either group is empty."""
    if n_a == 0 or n_b == 0:
        return None
    pa, pb = successes_a / n_a, successes_b / n_b
    se = math.sqrt(pa * (1 - pa) / n_a + pb * (1 - pb) / n_b)
    diff = pa - pb
    return Interval(diff, diff - Z95 * se, diff + Z95 * se)


def zscores(values: Sequence[float]) -> list[float]:
    m = mean(values)
    s = sample_std(values)
    if m is None or not s:
        return [0.0 for _ in values]
    return [(v - m) / s for v in values]
