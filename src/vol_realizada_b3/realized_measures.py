"""Medidas diarias de volatilidade realizada."""

from __future__ import annotations

from math import gamma, pi, sqrt
from typing import Any, Iterable

import numpy as np
import pandas as pd

from .config import PROJECT_ROOT, load_config
from .jumps import jump_test, jump_variation
from .utils import save_csv


def _finite_returns(returns: Iterable[float]) -> np.ndarray:
    values = np.asarray(list(returns), dtype=float)
    return values[np.isfinite(values)]


def mu_p(power: float) -> float:
    """Momento absoluto de ordem p de uma normal padrao."""
    return 2 ** (power / 2) * gamma((power + 1) / 2) / gamma(0.5)


def realized_variance(returns: Iterable[float]) -> float:
    """RV = soma dos quadrados dos retornos intradiarios."""
    values = _finite_returns(returns)
    return float(np.square(values).sum())


def realized_volatility(returns: Iterable[float]) -> float:
    """RVol diaria = raiz quadrada da RV."""
    return sqrt(realized_variance(returns))


def bipower_variation(returns: Iterable[float]) -> float:
    """Calcula a bipower variation diaria com correcao de amostra."""
    values = _finite_returns(returns)
    observations = len(values)
    if observations < 2:
        return float("nan")
    adjacent_products = np.abs(values[1:]) * np.abs(values[:-1])
    mu_1 = sqrt(2 / pi)
    return float(
        mu_1 ** -2
        * (observations / (observations - 1))
        * adjacent_products.sum()
    )


def tripower_quarticity(returns: Iterable[float]) -> float:
    """Calcula tripower quarticity com potencia 4/3."""
    values = _finite_returns(returns)
    observations = len(values)
    if observations < 3:
        return float("nan")
    powered = np.abs(values) ** (4 / 3)
    triple_products = powered[:-2] * powered[1:-1] * powered[2:]
    return float(
        observations
        * mu_p(4 / 3) ** -3
        * (observations / (observations - 2))
        * triple_products.sum()
    )


def compute_daily_measures(
    intraday: pd.DataFrame,
    annualization_days: int = 252,
    jump_alpha: float = 0.99,
    min_observations: int = 40,
) -> pd.DataFrame:
    """Agrega retornos intradiarios em medidas por ticker-dia."""
    rows: list[dict[str, Any]] = []
    data = intraday.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce")

    for (ticker, date), group in data.groupby(["ticker", "date"], sort=True):
        returns = _finite_returns(group["log_return"])
        observations = len(returns)
        if observations < min_observations:
            continue
        rv = realized_variance(returns)
        bv = bipower_variation(returns)
        tq = tripower_quarticity(returns)
        jv = jump_variation(rv, bv)
        test = jump_test(rv, bv, tq, observations, jump_alpha)
        rows.append(
            {
                "ticker": ticker,
                "date": date,
                "n_intraday_returns": observations,
                "rv": rv,
                "rvol_daily": sqrt(rv),
                "rvol_annualized": sqrt(annualization_days * rv),
                "bv": bv,
                "tq": tq,
                "jv": jv,
                "jump_share": jv / rv if rv > 0 else np.nan,
                "jump_z": test["jump_z"],
                "jump_critical_value": test["critical_value"],
                "jump_day": test["jump_day"],
                "jump_test_status": test["status"],
            }
        )
    return pd.DataFrame(rows)


def run_realized_measures(
    config: dict[str, Any] | None = None,
) -> pd.DataFrame:
    """Calcula e salva as medidas realizadas."""
    config = config or load_config()
    intraday = pd.read_csv(
        PROJECT_ROOT / "data" / "processed" / "intraday_returns.csv",
        parse_dates=["datetime", "date"],
    )
    settings = config["volatility"]
    measures = compute_daily_measures(
        intraday,
        annualization_days=settings["annualization_days"],
        jump_alpha=settings["jump_test_alpha"],
        min_observations=settings["min_intraday_obs_per_day"],
    )
    save_csv(
        measures,
        PROJECT_ROOT / "data" / "processed" / "realized_measures.csv",
    )
    return measures

