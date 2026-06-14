"""Estimacao de GARCH(1,1) e comparacao com volatilidade realizada."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .config import PROJECT_ROOT, load_config
from .utils import save_csv, setup_logging


LOGGER = setup_logging(__name__)


def _parameter(params: pd.Series, prefix: str) -> float:
    matches = [name for name in params.index if str(name).startswith(prefix)]
    return float(params[matches[0]]) if matches else np.nan


def estimate_garch_for_ticker(
    ticker_data: pd.DataFrame,
    measures: pd.DataFrame,
    ticker: str,
    settings: dict[str, Any],
) -> tuple[dict[str, Any], pd.DataFrame]:
    """Ajusta um GARCH e retorna resumo e serie condicional."""
    returns = (
        ticker_data[["date", "daily_return_pct"]]
        .dropna()
        .sort_values("date")
        .copy()
    )
    observations = len(returns)
    if observations < settings["min_daily_observations"]:
        return (
            {
                "ticker": ticker,
                "omega": np.nan,
                "alpha": np.nan,
                "beta": np.nan,
                "alpha_plus_beta": np.nan,
                "log_likelihood": np.nan,
                "aic": np.nan,
                "bic": np.nan,
                "correlation_garch_realized": np.nan,
                "observations_used": observations,
                "fit_status": "insufficient_observations",
            },
            pd.DataFrame(),
        )

    try:
        from arch import arch_model

        model = arch_model(
            returns["daily_return_pct"],
            mean="Constant",
            vol="GARCH",
            p=settings["p"],
            q=settings["q"],
            dist=settings["distribution"],
            rescale=False,
        )
        result = model.fit(disp="off", show_warning=False)
        params = result.params
        alpha = _parameter(params, "alpha[")
        beta = _parameter(params, "beta[")
        series = returns.copy()
        series["ticker"] = ticker
        series["garch_vol_daily"] = (
            np.asarray(result.conditional_volatility, dtype=float) / 100
        )
        comparison = series.merge(
            measures.loc[
                measures["ticker"].eq(ticker),
                ["date", "rvol_daily"],
            ],
            on="date",
            how="left",
        )
        correlation = comparison[
            ["garch_vol_daily", "rvol_daily"]
        ].corr().iloc[0, 1]
        summary = {
            "ticker": ticker,
            "omega": float(params.get("omega", np.nan)),
            "alpha": alpha,
            "beta": beta,
            "alpha_plus_beta": alpha + beta,
            "log_likelihood": float(result.loglikelihood),
            "aic": float(result.aic),
            "bic": float(result.bic),
            "correlation_garch_realized": float(correlation),
            "observations_used": observations,
            "fit_status": (
                "ok" if bool(result.convergence_flag == 0) else "not_converged"
            ),
        }
        return summary, comparison
    except Exception as exc:  # noqa: BLE001
        LOGGER.exception("Falha no GARCH de %s", ticker)
        return (
            {
                "ticker": ticker,
                "omega": np.nan,
                "alpha": np.nan,
                "beta": np.nan,
                "alpha_plus_beta": np.nan,
                "log_likelihood": np.nan,
                "aic": np.nan,
                "bic": np.nan,
                "correlation_garch_realized": np.nan,
                "observations_used": observations,
                "fit_status": f"failed: {exc}",
            },
            pd.DataFrame(),
        )


def run_garch_models(
    config: dict[str, Any] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Estima GARCH para todos os ativos selecionados."""
    config = config or load_config()
    daily = pd.read_csv(
        PROJECT_ROOT / "data" / "processed" / "daily_prices_returns.csv",
        parse_dates=["date"],
    )
    measures = pd.read_csv(
        PROJECT_ROOT / "data" / "processed" / "realized_measures.csv",
        parse_dates=["date"],
    )
    summaries: list[dict[str, Any]] = []
    series_parts: list[pd.DataFrame] = []
    for ticker, ticker_data in daily.groupby("ticker", sort=True):
        summary, series = estimate_garch_for_ticker(
            ticker_data,
            measures,
            ticker,
            config["garch"],
        )
        summaries.append(summary)
        if not series.empty:
            series_parts.append(series)

    summary_frame = pd.DataFrame(summaries)
    series_frame = (
        pd.concat(series_parts, ignore_index=True)
        if series_parts
        else pd.DataFrame(
            columns=[
                "date",
                "daily_return_pct",
                "ticker",
                "garch_vol_daily",
                "rvol_daily",
            ]
        )
    )
    save_csv(
        summary_frame,
        PROJECT_ROOT / "outputs" / "tables" / "garch_summary.csv",
    )
    save_csv(
        series_frame,
        PROJECT_ROOT / "data" / "processed" / "garch_volatility.csv",
    )
    return summary_frame, series_frame
