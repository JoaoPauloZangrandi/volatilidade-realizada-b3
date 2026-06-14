"""Selecao objetiva da amostra com base na qualidade intradiaria."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .config import (
    PROJECT_ROOT,
    configured_tickers,
    load_config,
    ticker_groups,
)
from .utils import save_csv, setup_logging


LOGGER = setup_logging(__name__)


def _daily_valid_mask(
    quality: pd.DataFrame,
    criteria: dict[str, Any],
) -> pd.Series:
    return (
        quality["candle_coverage"].ge(criteria["min_avg_candle_coverage"])
        & quality["valid_intraday_returns"].ge(
            criteria["min_intraday_returns_per_day"]
        )
        & quality["all_prices_positive"].fillna(False)
    )


def evaluate_sample_quality(
    quality: pd.DataFrame,
    synchronized: pd.DataFrame,
    config: dict[str, Any],
    download_status: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Produz uma linha de cobertura e decisao por ticker configurado."""
    criteria = config["sample_selection"]
    groups = ticker_groups(config)
    quality = quality.copy()
    quality["date"] = pd.to_datetime(quality["date"], errors="coerce")
    quality["day_valid"] = _daily_valid_mask(quality, criteria)

    download_lookup: dict[str, dict[str, Any]] = {}
    if download_status is not None and not download_status.empty:
        download_lookup = download_status.set_index("ticker").to_dict("index")

    rows: list[dict[str, Any]] = []
    for ticker in configured_tickers(config):
        ticker_quality = quality.loc[quality["ticker"].eq(ticker)].copy()
        ticker_data = synchronized.loc[synchronized["ticker"].eq(ticker)]
        download_info = download_lookup.get(ticker, {})

        if ticker_quality.empty:
            reason = download_info.get("error") or "sem dados intradiarios validos"
            rows.append(
                {
                    "ticker": ticker,
                    "grupo": groups[ticker],
                    "primeiro_dia": pd.NaT,
                    "ultimo_dia": pd.NaT,
                    "numero_dias": 0,
                    "numero_dias_validos": 0,
                    "numero_observacoes_intradiarias": 0,
                    "observacoes_medias_por_dia": 0.0,
                    "cobertura_media_candles": 0.0,
                    "proporcao_precos_parados": np.nan,
                    "positive_volume_share": 0.0,
                    "dias_removidos_falta_dados": 0,
                    "status": "excluded",
                    "razao_exclusao": reason,
                }
            )
            continue

        valid_days = int(ticker_quality["day_valid"].sum())
        total_days = int(len(ticker_quality))
        avg_coverage = float(ticker_quality["candle_coverage"].mean())
        avg_observations = float(ticker_quality["observed_candles"].mean())
        stale_share = float(
            ticker_data["log_return"].dropna().eq(0).mean()
        )
        volume_share = float(ticker_quality["positive_volume_share"].mean())
        all_positive = bool(ticker_quality["all_prices_positive"].all())

        reasons: list[str] = []
        if valid_days < criteria["min_valid_days"]:
            reasons.append(
                f"dias validos {valid_days} < {criteria['min_valid_days']}"
            )
        if avg_coverage < criteria["min_avg_candle_coverage"]:
            reasons.append(
                f"cobertura media {avg_coverage:.1%} abaixo do minimo"
            )
        if stale_share > criteria["max_stale_price_share"]:
            reasons.append(
                f"precos parados {stale_share:.1%} acima do maximo"
            )
        if volume_share < criteria.get("min_positive_volume_share", 0.0):
            reasons.append(
                f"volume positivo {volume_share:.1%} abaixo do minimo"
            )
        if criteria.get("require_positive_prices", True) and not all_positive:
            reasons.append("precos nao positivos")
        if download_info.get("status") == "unavailable":
            reasons.append(download_info.get("error") or "falha grave no download")

        rows.append(
            {
                "ticker": ticker,
                "grupo": groups[ticker],
                "primeiro_dia": ticker_quality["date"].min(),
                "ultimo_dia": ticker_quality["date"].max(),
                "numero_dias": total_days,
                "numero_dias_validos": valid_days,
                "numero_observacoes_intradiarias": int(
                    ticker_quality["observed_candles"].sum()
                ),
                "observacoes_medias_por_dia": avg_observations,
                "cobertura_media_candles": avg_coverage,
                "proporcao_precos_parados": stale_share,
                "positive_volume_share": volume_share,
                "dias_removidos_falta_dados": total_days - valid_days,
                "status": "included" if not reasons else "excluded",
                "razao_exclusao": "; ".join(reasons),
            }
        )
    return pd.DataFrame(rows)


def run_sample_selection(
    config: dict[str, Any] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Seleciona tickers e dias, gerando a base processada."""
    config = config or load_config()
    interim_dir = PROJECT_ROOT / "data" / "interim"
    synchronized = pd.read_csv(
        interim_dir / "intraday_synchronized.csv",
        parse_dates=["datetime", "date"],
    )
    quality = pd.read_csv(
        interim_dir / "daily_data_quality.csv",
        parse_dates=["date"],
    )
    status_path = PROJECT_ROOT / "data" / "raw" / "download_status.csv"
    download_status = pd.read_csv(status_path) if status_path.exists() else None

    coverage = evaluate_sample_quality(
        quality, synchronized, config, download_status
    )
    included = coverage.loc[coverage["status"].eq("included"), "ticker"].tolist()
    criteria = config["sample_selection"]
    quality["day_valid"] = _daily_valid_mask(quality, criteria)
    valid_pairs = quality.loc[quality["day_valid"], ["ticker", "date"]].copy()
    valid_pairs["date_key"] = valid_pairs["date"].dt.strftime("%Y-%m-%d")

    synchronized["date_key"] = pd.to_datetime(
        synchronized["date"], errors="coerce"
    ).dt.strftime("%Y-%m-%d")
    selected = synchronized.loc[synchronized["ticker"].isin(included)].merge(
        valid_pairs[["ticker", "date_key"]],
        on=["ticker", "date_key"],
        how="inner",
    )
    selected = selected.drop(columns=["date_key"]).sort_values(
        ["ticker", "datetime"]
    )

    daily_prices = (
        selected.sort_values("datetime")
        .groupby(["ticker", "date"], as_index=False)
        .agg(
            daily_close=("close", "last"),
            intraday_observations=("log_return", "count"),
        )
        .sort_values(["ticker", "date"])
    )
    daily_prices["daily_log_return"] = daily_prices.groupby("ticker")[
        "daily_close"
    ].transform(lambda values: np.log(values).diff())
    daily_prices["daily_return_pct"] = 100 * daily_prices["daily_log_return"]

    processed_dir = PROJECT_ROOT / "data" / "processed"
    tables_dir = PROJECT_ROOT / "outputs" / "tables"
    save_csv(selected, processed_dir / "intraday_returns.csv")
    save_csv(daily_prices, processed_dir / "daily_prices_returns.csv")
    save_csv(coverage, tables_dir / "data_coverage_by_ticker.csv")
    save_csv(
        coverage.loc[coverage["status"].eq("excluded")].rename(
            columns={
                "grupo": "group",
                "razao_exclusao": "motivo_exclusao",
                "cobertura_media_candles": "cobertura",
                "numero_dias_validos": "dias_validos",
                "observacoes_medias_por_dia": "observacoes_medias",
                "proporcao_precos_parados": "proporcao_preco_parado",
            }
        )[
            [
                "ticker",
                "group",
                "motivo_exclusao",
                "cobertura",
                "dias_validos",
                "observacoes_medias",
                "proporcao_preco_parado",
            ]
        ],
        tables_dir / "excluded_tickers.csv",
    )
    save_csv(
        coverage.loc[coverage["status"].eq("included"), ["ticker", "grupo"]],
        processed_dir / "selected_tickers.csv",
    )
    LOGGER.info(
        "Amostra final: %d incluidos de %d candidatos",
        len(included),
        len(coverage),
    )
    return coverage, selected

