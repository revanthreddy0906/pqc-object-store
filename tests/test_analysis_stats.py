"""The revision's statistics (analysis/stats.py) against textbook values."""

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "analysis"))
import stats


@pytest.mark.parametrize("df,p,expected", [
    (4, 0.975, 2.776), (4, 0.95, 2.132), (9, 0.975, 2.262), (9, 0.95, 1.833),
    (19, 0.975, 2.093), (19, 0.95, 1.729), (1, 0.975, 12.706),
])
def test_t_quantiles_match_the_table(df, p, expected):
    assert stats.t_quantile(p, df) == pytest.approx(expected, abs=5e-4)


def test_t_cdf_is_symmetric_and_monotone():
    assert stats.t_cdf(0.0, 7) == pytest.approx(0.5)
    assert stats.t_cdf(1.5, 7) + stats.t_cdf(-1.5, 7) == pytest.approx(1.0)
    assert stats.t_cdf(2.776, 4) == pytest.approx(0.975, abs=2e-5)
    assert stats.t_cdf(50.0, 30) == pytest.approx(1.0, abs=1e-12)


def test_tost_hand_computed_example():
    # d = log ratios with mean 0.01 and sd 0.02, n = 10 -> se = 0.0063246
    d = [0.01 + 0.02 * z for z in (-1.4863, -1.1560, -0.8257, -0.4954, -0.1651,
                                    0.1651, 0.4954, 0.8257, 1.1560, 1.4863)]
    result = stats.paired_tost(d)
    assert result.sd_log == pytest.approx(0.02, rel=1e-3)
    mean, se = 0.01, result.sd_log / math.sqrt(10)
    assert result.ratio == pytest.approx(math.exp(mean), rel=1e-9)
    t_lower = (mean - math.log(0.95)) / se
    t_upper = (mean - math.log(1.05)) / se
    assert result.p_lower == pytest.approx(1 - stats.t_cdf(t_lower, 9), rel=1e-6)
    assert result.p_upper == pytest.approx(stats.t_cdf(t_upper, 9), rel=1e-6)
    half = 1.833 * se
    assert result.ci90[0] == pytest.approx(math.exp(mean - half), rel=2e-4)
    assert result.ci90[1] == pytest.approx(math.exp(mean + half), rel=2e-4)
    assert result.p < 0.05          # CI90 = [0.998, 1.022] lies inside [0.95, 1.05]


def test_tost_decision_equals_ci90_inside_bounds():
    inside = stats.paired_tost([0.03, 0.035, 0.03, 0.04, 0.033])
    assert (inside.p < 0.05) == (inside.ci90[0] > 0.95 and inside.ci90[1] < 1.05)
    wide = stats.paired_tost([0.0, 0.09, -0.08, 0.05, -0.06])
    assert wide.p > 0.05 and not (wide.ci90[0] > 0.95 and wide.ci90[1] < 1.05)
    shifted = stats.paired_tost([0.08, 0.081, 0.079, 0.08, 0.082])   # clearly above +5 %
    assert shifted.p_upper > 0.95 and shifted.p > 0.05


def test_holm_adjustment():
    assert stats.holm([0.01, 0.04, 0.03]) == pytest.approx([0.03, 0.06, 0.06])
    assert stats.holm([0.5]) == [0.5]
    assert all(a >= p for a, p in zip(stats.holm([0.001, 0.2, 0.02, 0.04]), [0.001, 0.2, 0.02, 0.04]))


def test_power_grows_with_repetitions():
    low = stats.tost_power(0.035, 5, draws=1500)
    high = stats.tost_power(0.035, 20, draws=1500)
    assert low < high and high > 0.9


def test_state_dependent_queue_reduces_to_mm1():
    lam, mu = 60.0, 100.0
    assert stats.state_dependent_response(lam, lambda n: mu) == pytest.approx(1 / (mu - lam), rel=1e-6)


def test_state_dependent_queue_reduces_to_mmc():
    lam, service, servers = 3500.0, 0.005, 25           # the paper's M/M/c setting
    offered = lam * service
    term, total = 1.0, 1.0                              # Erlang C by its definition
    for k in range(1, servers):
        term *= offered / k
        total += term
    last = term * offered / servers * servers / (servers - offered)
    erlang_c = last / (total + last)
    expected = service + erlang_c * service / (servers - offered)
    got = stats.state_dependent_response(lam, lambda n: min(n, servers) / service)
    assert got == pytest.approx(expected, rel=1e-6)


def test_state_dependent_queue_is_unstable_above_capacity():
    assert stats.state_dependent_response(120.0, lambda n: 100.0) == float("inf")
    assert stats.state_dependent_response(100.0, lambda n: 100.0) == float("inf")


def test_interpolated_service_rate():
    mu = stats.interpolate_rate({1: 300.0, 32: 4000.0, 128: 4700.0})
    assert mu(1) == 300.0 and mu(32) == 4000.0 and mu(500) == 4700.0
    assert mu(80) == pytest.approx(4000 + 700 * 48 / 96)
