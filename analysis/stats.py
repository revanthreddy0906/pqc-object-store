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

import itertools
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


# ---------------------------------------------------------------- queueing

def state_dependent_response(arrival_rate: float, service_rate, max_state: int = 200_000) -> float:
    """Mean response time of a birth-death queue with Poisson arrivals at `arrival_rate`
    and total service rate `service_rate(n)` when n requests are in the system.

    The stationary distribution is p_n proportional to prod_{k<=n} arrival_rate / mu(k);
    the mean number in system L gives W = L / arrival_rate (Little's law). Returns inf
    when the queue is unstable (the tail does not decay). M/M/1 and M/M/c are the special
    cases mu(n) = mu and mu(n) = min(n, c) / S.
    """
    if arrival_rate <= 0:
        return float("nan")
    log_p, log_terms, tail_ratio = 0.0, [0.0], 0.0
    for n in range(1, max_state + 1):
        tail_ratio = arrival_rate / service_rate(n)
        log_p += math.log(tail_ratio)
        log_terms.append(log_p)
        if tail_ratio < 1 and log_p < log_terms[0] - 60 and n > 16:   # negligible mass beyond
            break
    else:
        return float("inf")
    if tail_ratio >= 1:
        return float("inf")
    peak = max(log_terms)
    weights = [math.exp(v - peak) for v in log_terms]
    total = sum(weights)
    mean_in_system = sum(n * w for n, w in enumerate(weights)) / total
    return mean_in_system / arrival_rate


def interpolate_rate(points: dict[int, float]):
    """mu(n) from measured closed-loop throughput at some concurrency levels: linear between
    measured levels, constant beyond the largest (more waiting requests do not add capacity)."""
    levels = sorted(points)

    def mu(n: int) -> float:
        if n <= levels[0]:
            return points[levels[0]] * n / levels[0]
        if n >= levels[-1]:
            return points[levels[-1]]
        for low, high in itertools.pairwise(levels):
            if low <= n <= high:
                return points[low] + (points[high] - points[low]) * (n - low) / (high - low)
        return points[levels[-1]]

    return mu
