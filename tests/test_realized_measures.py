import math

import numpy as np

from vol_realizada_b3.realized_measures import (
    bipower_variation,
    realized_variance,
    realized_volatility,
)


def test_realized_variance_simple_case() -> None:
    returns = np.array([0.01, -0.02, 0.03])
    assert realized_variance(returns) == np.sum(returns**2)


def test_realized_volatility_simple_case() -> None:
    returns = np.array([0.01, -0.02, 0.03])
    expected = math.sqrt(np.sum(returns**2))
    assert realized_volatility(returns) == expected


def test_bipower_variation_positive() -> None:
    value = bipower_variation([0.01, -0.02, 0.015, -0.005])
    assert np.isfinite(value)
    assert value > 0

