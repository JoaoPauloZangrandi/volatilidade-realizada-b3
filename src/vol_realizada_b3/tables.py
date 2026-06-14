"""Construcao das tabelas finais do trabalho."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .config import PROJECT_ROOT, load_config
from .utils import save_csv


def descriptive_intraday_returns(intraday: pd.DataFrame) -> pd.DataFrame:
    """Estatisticas descritivas dos retornos intradiarios por ticker."""
    rows: list[dict[str, Any]] = []
    for ticker, group in intraday.groupby("ticker", sort=True):
        values = pd.to_numeric(group["log_return"], errors="coerce").dropna()
        rows.append(
            {
                "ticker": ticker,
                "mean": values.mean(),
                "std": values.std(),
                "skewness": values.skew(),
                "kurtosis": values.kurt(),
                "min": values.min(),
                "p1": values.quantile(0.01),
                "p5": values.quantile(0.05),
                "median": values.median(),
                "p95": values.quantile(0.95),
                "p99": values.quantile(0.99),
                "max": values.max(),
                "observations": len(values),
            }
        )
    return pd.DataFrame(rows)


def realized_summary(measures: pd.DataFrame) -> pd.DataFrame:
    """Resumo das medidas realizadas por ativo."""
    rows: list[dict[str, Any]] = []
    for ticker, group in measures.groupby("ticker", sort=True):
        rows.append(
            {
                "ticker": ticker,
                "mean_rv": group["rv"].mean(),
                "mean_rvol_daily": group["rvol_daily"].mean(),
                "mean_rvol_annualized": group["rvol_annualized"].mean(),
                "median_rvol_annualized": group["rvol_annualized"].median(),
                "p90_rvol_annualized": group["rvol_annualized"].quantile(0.90),
                "p95_rvol_annualized": group["rvol_annualized"].quantile(0.95),
                "max_rvol_annualized": group["rvol_annualized"].max(),
                "mean_bv": group["bv"].mean(),
                "mean_jv": group["jv"].mean(),
                "days": len(group),
            }
        )
    return pd.DataFrame(rows)


def jump_summary(measures: pd.DataFrame) -> pd.DataFrame:
    """Frequencia, intensidade e maior jump por ticker."""
    rows: list[dict[str, Any]] = []
    for ticker, group in measures.groupby("ticker", sort=True):
        valid_share = group["jump_share"].dropna()
        max_index = valid_share.idxmax() if not valid_share.empty else None
        rows.append(
            {
                "ticker": ticker,
                "total_days": len(group),
                "jump_days": int(group["jump_day"].fillna(False).sum()),
                "jump_day_percentage": float(group["jump_day"].mean()),
                "mean_jump_share": valid_share.mean(),
                "max_jump_share": valid_share.max(),
                "max_jump_date": (
                    group.loc[max_index, "date"] if max_index is not None else pd.NaT
                ),
                "max_jump_z": group["jump_z"].max(),
            }
        )
    return pd.DataFrame(rows)


def group_comparison(
    measures: pd.DataFrame,
    coverage: pd.DataFrame,
) -> pd.DataFrame:
    """Compara as amostras core e complementar selecionada."""
    merged = measures.merge(
        coverage[["ticker", "grupo", "status"]],
        on="ticker",
        how="left",
    )
    merged = merged.loc[merged["status"].eq("included")]
    return (
        merged.groupby("grupo", as_index=False)
        .agg(
            tickers=("ticker", "nunique"),
            ticker_days=("date", "size"),
            mean_rvol_daily=("rvol_daily", "mean"),
            mean_rvol_annualized=("rvol_annualized", "mean"),
            jump_frequency=("jump_day", "mean"),
            mean_jump_share=("jump_share", "mean"),
        )
        .sort_values("grupo")
    )


def asset_ranking(
    realized: pd.DataFrame,
    jumps: pd.DataFrame,
    garch: pd.DataFrame,
    coverage: pd.DataFrame,
) -> pd.DataFrame:
    """Combina rankings de risco e adiciona interpretacao curta."""
    ranking = realized[
        ["ticker", "mean_rvol_annualized"]
    ].merge(
        jumps[["ticker", "jump_day_percentage", "mean_jump_share"]],
        on="ticker",
        how="outer",
    )
    if not garch.empty:
        ranking = ranking.merge(
            garch[["ticker", "alpha_plus_beta"]],
            on="ticker",
            how="left",
        )
    else:
        ranking["alpha_plus_beta"] = np.nan
    ranking = ranking.merge(
        coverage[["ticker", "grupo"]],
        on="ticker",
        how="left",
    )
    ranking["rank_mean_realized_volatility"] = ranking[
        "mean_rvol_annualized"
    ].rank(ascending=False, method="min")
    ranking["rank_jump_frequency"] = ranking[
        "jump_day_percentage"
    ].rank(ascending=False, method="min")
    ranking["rank_mean_jump_share"] = ranking[
        "mean_jump_share"
    ].rank(ascending=False, method="min")
    ranking["rank_garch_persistence"] = ranking[
        "alpha_plus_beta"
    ].rank(ascending=False, method="min", na_option="bottom")

    median_rvol = ranking["mean_rvol_annualized"].median()
    median_jump = ranking["jump_day_percentage"].median()

    def interpretation(row: pd.Series) -> str:
        risk = "volatilidade acima da mediana" if (
            row["mean_rvol_annualized"] >= median_rvol
        ) else "volatilidade abaixo da mediana"
        jumps_text = "maior incidencia relativa de jumps" if (
            row["jump_day_percentage"] >= median_jump
        ) else "menor incidencia relativa de jumps"
        return f"{risk}; {jumps_text}; grupo {row['grupo']}"

    ranking["interpretation"] = ranking.apply(interpretation, axis=1)
    return ranking.sort_values(
        "rank_mean_realized_volatility"
    ).reset_index(drop=True)


def run_tables(
    config: dict[str, Any] | None = None,
) -> dict[str, pd.DataFrame]:
    """Gera CSVs obrigatorios e um workbook de apoio."""
    config = config or load_config()
    del config
    intraday = pd.read_csv(
        PROJECT_ROOT / "data" / "processed" / "intraday_returns.csv"
    )
    measures = pd.read_csv(
        PROJECT_ROOT / "data" / "processed" / "realized_measures.csv",
        parse_dates=["date"],
    )
    coverage = pd.read_csv(
        PROJECT_ROOT / "outputs" / "tables" / "data_coverage_by_ticker.csv"
    )
    garch_path = PROJECT_ROOT / "outputs" / "tables" / "garch_summary.csv"
    garch = pd.read_csv(garch_path) if garch_path.exists() else pd.DataFrame()

    tables = {
        "descriptive_intraday_returns": descriptive_intraday_returns(intraday),
        "realized_measures_summary": realized_summary(measures),
        "jump_summary": jump_summary(measures),
        "group_comparison": group_comparison(measures, coverage),
    }
    tables["asset_ranking_risk"] = asset_ranking(
        tables["realized_measures_summary"],
        tables["jump_summary"],
        garch,
        coverage,
    )

    tables_dir = PROJECT_ROOT / "outputs" / "tables"
    for name, table in tables.items():
        save_csv(table, tables_dir / f"{name}.csv")

    workbook_path = tables_dir / "tabelas_volatilidade_realizada_b3.xlsx"
    with pd.ExcelWriter(workbook_path, engine="openpyxl") as writer:
        for name, table in {
            "coverage": coverage,
            "garch": garch,
            **tables,
        }.items():
            table.to_excel(writer, sheet_name=name[:31], index=False)
    return tables

