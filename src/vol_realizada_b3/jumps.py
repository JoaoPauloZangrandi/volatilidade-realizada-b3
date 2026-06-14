"""Jump variation e teste estatistico inspirado em BNS."""

from __future__ import annotations

from math import pi, sqrt
from typing import Any

import numpy as np
from scipy.stats import norm


def jump_variation(realized_variance: float, bipower_variation: float) -> float:
    """JV = max(RV - BV, 0), preservando NaN quando necessario."""
    if not np.isfinite(realized_variance) or not np.isfinite(bipower_variation):
        return float("nan")
    return float(max(realized_variance - bipower_variation, 0.0))


def jump_test_statistic(
    realized_variance: float,
    bipower_variation: float,
    tripower_quarticity: float,
    observations: int,
) -> float:
    """Calcula a estatistica padronizada do teste de jump."""
    if (
        observations < 3
        or not np.isfinite(realized_variance)
        or not np.isfinite(bipower_variation)
        or not np.isfinite(tripower_quarticity)
        or realized_variance <= 0
        or bipower_variation <= 0
    ):
        return float("nan")

    variance_constant = (pi / 2) ** 2 + pi - 5
    quarticity_ratio = max(
        1.0,
        tripower_quarticity / (bipower_variation**2),
    )
    denominator = sqrt(
        variance_constant * (1 / observations) * quarticity_ratio
    )
    if denominator <= 0 or not np.isfinite(denominator):
        return float("nan")
    return float(
        ((realized_variance - bipower_variation) / realized_variance)
        / denominator
    )


def jump_test(
    realized_variance: float,
    bipower_variation: float,
    tripower_quarticity: float,
    observations: int,
    alpha: float = 0.99,
) -> dict[str, Any]:
    """Classifica jump day e documenta casos numericamente instaveis."""
    if not 0.5 < alpha < 1:
        raise ValueError("alpha deve estar entre 0.5 e 1")
    critical_value = float(norm.ppf(alpha))
    statistic = jump_test_statistic(
        realized_variance,
        bipower_variation,
        tripower_quarticity,
        observations,
    )
    if not np.isfinite(statistic):
        return {
            "jump_z": np.nan,
            "critical_value": critical_value,
            "jump_day": False,
            "status": "insufficient_or_unstable",
        }
    return {
        "jump_z": statistic,
        "critical_value": critical_value,
        "jump_day": bool(statistic > critical_value),
        "status": "ok",
    }

