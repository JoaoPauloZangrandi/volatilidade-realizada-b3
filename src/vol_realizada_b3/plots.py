"""Graficos finais em matplotlib."""

from __future__ import annotations

from math import ceil
from pathlib import Path
from typing import Any

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .config import PROJECT_ROOT, load_config


COLORS = {
    "blue": "#1F4E78",
    "light_blue": "#4C78A8",
    "red": "#C43C39",
    "orange": "#F28E2B",
    "green": "#2E7D32",
    "gray": "#6B7280",
}


def _style() -> None:
    plt.rcParams.update(
        {
            "font.size": 10,
            "axes.titlesize": 13,
            "axes.labelsize": 10,
            "legend.fontsize": 8,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.grid": True,
            "grid.alpha": 0.2,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )


def _save(figure: plt.Figure, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(figure)


def plot_rvol_time_series(measures: pd.DataFrame, path: Path) -> None:
    figure, axis = plt.subplots(figsize=(12, 6))
    for ticker, group in measures.groupby("ticker"):
        axis.plot(
            group["date"],
            100 * group["rvol_annualized"],
            label=ticker.replace(".SA", ""),
            linewidth=1.2,
            alpha=0.85,
        )
    axis.set_title("Volatilidade realizada anualizada por ativo")
    axis.set_xlabel("Data")
    axis.set_ylabel("RVol anualizada (%)")
    axis.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
    axis.legend(ncol=4, frameon=False)
    figure.autofmt_xdate()
    _save(figure, path)


def plot_rv_vs_bv(measures: pd.DataFrame, path: Path) -> None:
    tickers = list(measures["ticker"].drop_duplicates())
    columns = 2
    rows = ceil(len(tickers) / columns)
    figure, axes = plt.subplots(
        rows,
        columns,
        figsize=(13, max(4, rows * 3)),
        squeeze=False,
        sharex=False,
    )
    for axis, ticker in zip(axes.flat, tickers):
        group = measures.loc[measures["ticker"].eq(ticker)]
        axis.plot(group["date"], group["rv"], label="RV", color=COLORS["blue"])
        axis.plot(group["date"], group["bv"], label="BV", color=COLORS["orange"])
        axis.set_title(ticker)
        axis.set_ylabel("Variacao")
        axis.legend(frameon=False)
        axis.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
    for axis in axes.flat[len(tickers) :]:
        axis.set_axis_off()
    figure.suptitle("Realized Variance versus Bipower Variation", y=1.0)
    figure.tight_layout()
    _save(figure, path)


def plot_jump_days(measures: pd.DataFrame, path: Path) -> None:
    tickers = list(measures["ticker"].drop_duplicates())
    columns = 2
    rows = ceil(len(tickers) / columns)
    figure, axes = plt.subplots(
        rows,
        columns,
        figsize=(13, max(4, rows * 3)),
        squeeze=False,
    )
    for axis, ticker in zip(axes.flat, tickers):
        group = measures.loc[measures["ticker"].eq(ticker)]
        axis.plot(
            group["date"],
            100 * group["rvol_annualized"],
            color=COLORS["blue"],
            linewidth=1.2,
        )
        jumps = group.loc[group["jump_day"].fillna(False)]
        axis.scatter(
            jumps["date"],
            100 * jumps["rvol_annualized"],
            color=COLORS["red"],
            s=24,
            zorder=3,
            label="Jump day",
        )
        axis.set_title(ticker)
        axis.set_ylabel("RVol anualizada (%)")
        if not jumps.empty:
            axis.legend(frameon=False)
        axis.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
    for axis in axes.flat[len(tickers) :]:
        axis.set_axis_off()
    figure.suptitle("Dias classificados como jump na volatilidade realizada", y=1.0)
    figure.tight_layout()
    _save(figure, path)


def plot_boxplot(measures: pd.DataFrame, path: Path) -> None:
    ordered = (
        measures.groupby("ticker")["rvol_annualized"]
        .median()
        .sort_values(ascending=False)
        .index
    )
    values = [
        100
        * measures.loc[
            measures["ticker"].eq(ticker), "rvol_annualized"
        ].dropna()
        for ticker in ordered
    ]
    figure, axis = plt.subplots(figsize=(11, 6))
    box = axis.boxplot(values, tick_labels=ordered, patch_artist=True)
    for patch in box["boxes"]:
        patch.set_facecolor(COLORS["light_blue"])
        patch.set_alpha(0.75)
    axis.set_title("Distribuicao da volatilidade realizada anualizada")
    axis.set_ylabel("RVol anualizada (%)")
    axis.tick_params(axis="x", rotation=45)
    _save(figure, path)


def plot_correlation_heatmap(measures: pd.DataFrame, path: Path) -> None:
    pivot = measures.pivot(index="date", columns="ticker", values="rvol_daily")
    correlation = pivot.corr(min_periods=5)
    figure, axis = plt.subplots(figsize=(9, 7))
    image = axis.imshow(correlation, vmin=-1, vmax=1, cmap="RdBu_r")
    axis.set_xticks(range(len(correlation.columns)))
    axis.set_yticks(range(len(correlation.index)))
    axis.set_xticklabels(correlation.columns, rotation=45, ha="right")
    axis.set_yticklabels(correlation.index)
    for row in range(len(correlation.index)):
        for column in range(len(correlation.columns)):
            value = correlation.iloc[row, column]
            if np.isfinite(value):
                axis.text(
                    column,
                    row,
                    f"{value:.2f}",
                    ha="center",
                    va="center",
                    fontsize=7,
                    color="white" if abs(value) > 0.55 else "black",
                )
    figure.colorbar(image, ax=axis, label="Correlacao")
    axis.set_title("Correlacao entre volatilidades realizadas")
    figure.tight_layout()
    _save(figure, path)


def plot_jump_frequency(jump_table: pd.DataFrame, path: Path) -> None:
    data = jump_table.sort_values("jump_day_percentage", ascending=True)
    figure, axis = plt.subplots(figsize=(10, 5.5))
    axis.barh(
        data["ticker"],
        100 * data["jump_day_percentage"],
        color=COLORS["red"],
        alpha=0.85,
    )
    axis.set_title("Frequencia de dias com jumps")
    axis.set_xlabel("Jump days (% dos dias)")
    _save(figure, path)


def plot_garch_comparisons(garch: pd.DataFrame, output_dir: Path) -> None:
    if garch.empty:
        return
    tickers = list(garch["ticker"].drop_duplicates())
    rows = ceil(len(tickers) / 2)
    combined, axes = plt.subplots(
        rows,
        2,
        figsize=(13, max(4, rows * 3)),
        squeeze=False,
    )
    for axis, ticker in zip(axes.flat, tickers):
        group = garch.loc[garch["ticker"].eq(ticker)].sort_values("date")
        axis.plot(
            group["date"],
            100 * group["rvol_daily"],
            label="Realizada intradiaria",
            color=COLORS["blue"],
        )
        axis.plot(
            group["date"],
            100 * group["garch_vol_daily"],
            label="GARCH(1,1)",
            color=COLORS["orange"],
        )
        axis.set_title(ticker)
        axis.set_ylabel("Volatilidade diaria (%)")
        axis.legend(frameon=False)
        axis.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))

        single, single_axis = plt.subplots(figsize=(10, 5))
        single_axis.plot(
            group["date"],
            100 * group["rvol_daily"],
            label="Realizada intradiaria",
            color=COLORS["blue"],
        )
        single_axis.plot(
            group["date"],
            100 * group["garch_vol_daily"],
            label="GARCH(1,1)",
            color=COLORS["orange"],
        )
        single_axis.set_title(f"GARCH versus volatilidade realizada - {ticker}")
        single_axis.set_xlabel("Data")
        single_axis.set_ylabel("Volatilidade diaria (%)")
        single_axis.legend(frameon=False)
        single_axis.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
        single.autofmt_xdate()
        _save(
            single,
            output_dir
            / f"garch_vs_realized_{ticker.replace('.', '_').lower()}.png",
        )

    for axis in axes.flat[len(tickers) :]:
        axis.set_axis_off()
    combined.suptitle("GARCH(1,1) versus volatilidade realizada", y=1.0)
    combined.tight_layout()
    _save(combined, output_dir / "garch_vs_realized_all.png")


def plot_risk_ranking(ranking: pd.DataFrame, path: Path) -> None:
    data = ranking.sort_values("mean_rvol_annualized", ascending=True)
    colors = [
        COLORS["red"]
        if group == "high_vol_growth_candidate"
        else COLORS["blue"]
        for group in data["grupo"]
    ]
    figure, axis = plt.subplots(figsize=(10, 6))
    axis.barh(
        data["ticker"],
        100 * data["mean_rvol_annualized"],
        color=colors,
        alpha=0.85,
    )
    axis.set_title("Ranking de risco por volatilidade realizada media")
    axis.set_xlabel("RVol anualizada media (%)")
    _save(figure, path)


def plot_coverage(coverage: pd.DataFrame, path: Path) -> None:
    data = coverage.sort_values("cobertura_media_candles", ascending=True)
    colors = [
        COLORS["green"] if status == "included" else COLORS["gray"]
        for status in data["status"]
    ]
    figure, axis = plt.subplots(figsize=(10, 6))
    axis.barh(
        data["ticker"],
        100 * data["cobertura_media_candles"],
        color=colors,
        alpha=0.85,
    )
    axis.axvline(70, color=COLORS["red"], linestyle="--", label="Minimo 70%")
    axis.set_title("Cobertura media de candles por ativo")
    axis.set_xlabel("Cobertura (%)")
    axis.legend(frameon=False)
    _save(figure, path)


def plot_intraday_signature(
    intraday: pd.DataFrame,
    coverage: pd.DataFrame,
    path: Path,
) -> None:
    groups = coverage[["ticker", "grupo"]]
    data = intraday.merge(groups, on="ticker", how="left")
    data["abs_return"] = data["log_return"].abs()
    data["squared_return"] = data["log_return"] ** 2
    signature = (
        data.groupby(["grupo", "time"], as_index=False)
        .agg(
            mean_abs_return=("abs_return", "mean"),
            mean_squared_return=("squared_return", "mean"),
        )
        .sort_values("time")
    )
    figure, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    palette = {
        "core_liquid": COLORS["blue"],
        "high_vol_growth_candidate": COLORS["red"],
    }
    labels = {
        "core_liquid": "Core/liquida",
        "high_vol_growth_candidate": "Growth/high-vol",
    }
    for group, frame in signature.groupby("grupo"):
        color = palette.get(group, COLORS["gray"])
        axes[0].plot(
            frame["time"],
            100 * frame["mean_abs_return"],
            label=labels.get(group, group),
            color=color,
        )
        axes[1].plot(
            frame["time"],
            10000 * frame["mean_squared_return"],
            label=labels.get(group, group),
            color=color,
        )
    axes[0].set_title("Assinatura intradiaria: retorno absoluto medio")
    axes[0].set_ylabel("|retorno| medio (%)")
    axes[1].set_title("Assinatura intradiaria: retorno quadratico medio")
    axes[1].set_ylabel("Retorno ao quadrado (x 10.000)")
    axes[1].set_xlabel("Horario")
    tick_positions = np.arange(0, signature["time"].nunique(), 12)
    unique_times = sorted(signature["time"].dropna().unique())
    axes[1].set_xticks(tick_positions)
    axes[1].set_xticklabels(
        [unique_times[index] for index in tick_positions if index < len(unique_times)],
        rotation=45,
    )
    axes[0].legend(frameon=False)
    figure.tight_layout()
    _save(figure, path)


def plot_group_comparison(groups: pd.DataFrame, path: Path) -> None:
    figure, axes = plt.subplots(1, 3, figsize=(13, 4.5))
    metrics = [
        ("mean_rvol_annualized", "RVol anualizada media (%)", 100),
        ("jump_frequency", "Frequencia de jump days (%)", 100),
        ("mean_jump_share", "Jump share medio (%)", 100),
    ]
    colors = [
        COLORS["blue"] if group == "core_liquid" else COLORS["red"]
        for group in groups["grupo"]
    ]
    labels = groups["grupo"].replace(
        {
            "core_liquid": "Core/liquida",
            "high_vol_growth_candidate": "Growth/high-vol",
        }
    )
    for axis, (column, title, scale) in zip(axes, metrics):
        axis.bar(labels, scale * groups[column], color=colors, alpha=0.85)
        axis.set_title(title)
        axis.tick_params(axis="x", rotation=20)
    figure.suptitle("Comparacao entre os grupos selecionados")
    figure.tight_layout()
    _save(figure, path)


def run_plots(config: dict[str, Any] | None = None) -> None:
    """Gera todos os graficos obrigatorios."""
    config = config or load_config()
    del config
    _style()
    figures = PROJECT_ROOT / "outputs" / "figures"
    measures = pd.read_csv(
        PROJECT_ROOT / "data" / "processed" / "realized_measures.csv",
        parse_dates=["date"],
    )
    intraday = pd.read_csv(
        PROJECT_ROOT / "data" / "processed" / "intraday_returns.csv",
        parse_dates=["datetime", "date"],
    )
    coverage = pd.read_csv(
        PROJECT_ROOT / "outputs" / "tables" / "data_coverage_by_ticker.csv"
    )
    jumps = pd.read_csv(
        PROJECT_ROOT / "outputs" / "tables" / "jump_summary.csv"
    )
    ranking = pd.read_csv(
        PROJECT_ROOT / "outputs" / "tables" / "asset_ranking_risk.csv"
    )
    groups = pd.read_csv(
        PROJECT_ROOT / "outputs" / "tables" / "group_comparison.csv"
    )
    garch_path = PROJECT_ROOT / "data" / "processed" / "garch_volatility.csv"
    garch = (
        pd.read_csv(garch_path, parse_dates=["date"])
        if garch_path.exists()
        else pd.DataFrame()
    )

    plot_rvol_time_series(measures, figures / "realized_volatility_time_series.png")
    plot_rv_vs_bv(measures, figures / "rv_vs_bv.png")
    plot_jump_days(measures, figures / "jump_days_realized_volatility.png")
    plot_boxplot(measures, figures / "rvol_boxplot_by_ticker.png")
    plot_correlation_heatmap(measures, figures / "rvol_correlation_heatmap.png")
    plot_jump_frequency(jumps, figures / "jump_frequency_by_ticker.png")
    plot_garch_comparisons(garch, figures)
    plot_risk_ranking(ranking, figures / "asset_risk_ranking.png")
    plot_coverage(coverage, figures / "data_coverage_by_ticker.png")
    plot_intraday_signature(
        intraday,
        coverage,
        figures / "intraday_volatility_signature.png",
    )
    plot_group_comparison(groups, figures / "core_vs_high_vol_comparison.png")

