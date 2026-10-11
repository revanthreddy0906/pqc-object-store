"""Statistics for the revision analysis (SoT v1.8): Student-t distribution, paired TOST on
log ratios, and the Holm correction. Standard library only, so the analysis has no
dependency beyond numpy/matplotlib.

Paired TOST (two one-sided tests) for equivalence of two modes a and b: with paired log
ratios d_i = log(x_a,i / x_b,i) over n repetitions and bounds [log(lo), log(hi)],

    H0 lower: mean(d) <= log(lo)      t_lower = (mean - log(lo)) / se,  p = P(T >= t_lower)
    H0 upper: mean(d) >= log(hi)      t_upper = (mean - log(hi)) / se,  p = P(T <= t_upper)

Equivalence is declared when both are rejected, i.e. p = max(p_lower, p_upper) < alpha,
which is the same as the (1 - 2 alpha) confidence interval lying inside the bounds.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass


def _betacf(a: float, b: float, x: float) -> float:
    """Continued fraction for the incomplete beta function (Lentz's method)."""
    tiny, qab, qap, qam = 1e-300, a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 400):
        m2 = 2 * m
        for aa in (m * (b - m) * x / ((qam + m2) * (a + m2)),
                   -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))):
            d = 1.0 + aa * d
            d = 1.0 / (d if abs(d) > tiny else tiny)
            c = 1.0 + aa / c
            c = c if abs(c) > tiny else tiny
            delta = d * c
            h *= delta
        if abs(delta - 1.0) < 1e-15:
            break
    return h


def _betainc(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta function I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    front = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
                     + a * math.log(x) + b * math.log1p(-x))
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def t_cdf(t: float, df: float) -> float:
    """P(T <= t) for Student's t with df degrees of freedom."""
    tail = 0.5 * _betainc(df / 2.0, 0.5, df / (df + t * t))
    return 1.0 - tail if t > 0 else tail


def t_quantile(p: float, df: float) -> float:
    """Inverse of t_cdf by bisection (p in (0, 1))."""
    lo, hi = -1e3, 1e3
    for _ in range(200):
        mid = (lo + hi) / 2
        if t_cdf(mid, df) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


@dataclass(frozen=True)
class Tost:
    n: int
    ratio: float            # exp(mean log ratio)
    ci90: tuple[float, float]   # decides equivalence at alpha = 0.05
    ci95: tuple[float, float]   # shown for estimation
    p_lower: float
    p_upper: float
    sd_log: float

    @property
    def p(self) -> float:
        return max(self.p_lower, self.p_upper)


def paired_tost(log_ratios: list[float], lower: float = 0.95, upper: float = 1.05) -> Tost | None:
    """Paired TOST on log ratios against the ratio bounds [lower, upper]."""
    values = [v for v in log_ratios if not math.isnan(v)]
    n = len(values)
    if n < 2:
        return None
    mean, sd = statistics.fmean(values), statistics.stdev(values)
    df = n - 1
    se = sd / math.sqrt(n)
    if se == 0:   # identical ratios in every repetition: the interval is a point
        inside = math.log(lower) < mean < math.log(upper)
        p_lower = p_upper = 0.0 if inside else 1.0
        return Tost(n, math.exp(mean), (math.exp(mean),) * 2, (math.exp(mean),) * 2,
                    p_lower, p_upper, 0.0)
    p_lower = 1.0 - t_cdf((mean - math.log(lower)) / se, df)
    p_upper = t_cdf((mean - math.log(upper)) / se, df)
    h90, h95 = t_quantile(0.95, df) * se, t_quantile(0.975, df) * se
    return Tost(n, math.exp(mean), (math.exp(mean - h90), math.exp(mean + h90)),
                (math.exp(mean - h95), math.exp(mean + h95)), p_lower, p_upper, sd)


def holm(p_values: list[float]) -> list[float]:
    """Holm step-down adjusted p-values, in the input order (family-wise error control)."""
    order = sorted(range(len(p_values)), key=lambda i: p_values[i])
    adjusted, running = [0.0] * len(p_values), 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (len(p_values) - rank) * p_values[i]))
        adjusted[i] = running
    return adjusted


def tost_power(sd_log: float, n: int, alpha: float = 0.05, lower: float = 0.95, upper: float = 1.05,
               true_ratio: float = 1.0, draws: int = 20000, seed: int = 1) -> float:
    """Simulated power of the paired TOST for normally distributed log ratios."""
    import random

    rng = random.Random(seed)
    mu, hits = math.log(true_ratio), 0
    for _ in range(draws):
        result = paired_tost([rng.gauss(mu, sd_log) for _ in range(n)], lower, upper)
        hits += result is not None and result.p < alpha
    return hits / draws
