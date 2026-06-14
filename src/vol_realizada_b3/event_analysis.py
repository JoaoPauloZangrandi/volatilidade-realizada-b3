"""Analise opcional de janelas de divulgacao de resultados."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .config import PROJECT_ROOT, load_config
from .utils import save_csv, setup_logging


LOGGER = setup_logging(__name__)
EVENT_COLUMNS = [
    "ticker",
    "event_date",
    "event_type",
    "event_description",
    "rvol_t_minus_1",
    "rvol_t",
    "rvol_t_plus_1",
    "jump_day_t_minus_1",
    "jump_day_t",
    "jump_day_t_plus_1",
    "normal_mean_rvol",
    "event_window_mean_rvol",
    "event_vs_normal_ratio",
    "normal_jump_frequency",
    "event_window_jump_frequency",
    "status",
]


def load_manual_events(path: Path) -> pd.DataFrame:
    """Le eventos manuais; cabecalho vazio e um caso valido."""
    if not path.exists():
        return pd.DataFrame(
            columns=["ticker", "date", "event_type", "event_description"]
        )
    try:
        events = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame(
            columns=["ticker", "date", "event_type", "event_description"]
        )
    required = {"ticker", "date", "event_type", "event_description"}
    if not required.issubset(events.columns):
        raise ValueError(
            f"events_earnings.csv deve conter: {sorted(required)}"
        )
    events = events.dropna(subset=["ticker", "date"]).copy()
    events["date"] = pd.to_datetime(events["date"], errors="coerce").dt.normalize()
    return events.dropna(subset=["date"])


def analyze_event_windows(
    events: pd.DataFrame,
    measures: pd.DataFrame,
) -> pd.DataFrame:
    """Compara t-1, t e t+1 com dias normais do mesmo ticker."""
    if events.empty or measures.empty:
        return pd.DataFrame(columns=EVENT_COLUMNS)

    data = measures.copy()
    data["date"] = pd.to_datetime(data["date"]).dt.normalize()
    rows: list[dict[str, Any]] = []

    for event in events.itertuples(index=False):
        ticker_data = (
            data.loc[data["ticker"].eq(event.ticker)]
            .sort_values("date")
            .reset_index(drop=True)
        )
        positions = ticker_data.index[ticker_data["date"].eq(event.date)].tolist()
        if not positions:
            rows.append(
                {
                    "ticker": event.ticker,
                    "event_date": event.date,
                    "event_type": event.event_type,
                    "event_description": event.event_description,
                    "status": "event_date_not_in_sample",
                }
            )
            continue

        position = positions[0]
        window_positions = [position - 1, position, position + 1]
        window = ticker_data.loc[
            [p for p in window_positions if 0 <= p < len(ticker_data)]
        ]
        normal = ticker_data.drop(
            index=[p for p in window_positions if 0 <= p < len(ticker_data)]
        )

        def value_at(offset: int, column: str) -> Any:
            target = position + offset
            if not 0 <= target < len(ticker_data):
                return np.nan
            return ticker_data.loc[target, column]

        normal_mean = float(normal["rvol_daily"].mean()) if not normal.empty else np.nan
        window_mean = float(window["rvol_daily"].mean())
        rows.append(
            {
                "ticker": event.ticker,
                "event_date": event.date,
                "event_type": event.event_type,
                "event_description": event.event_description,
                "rvol_t_minus_1": value_at(-1, "rvol_daily"),
                "rvol_t": value_at(0, "rvol_daily"),
                "rvol_t_plus_1": value_at(1, "rvol_daily"),
                "jump_day_t_minus_1": value_at(-1, "jump_day"),
                "jump_day_t": value_at(0, "jump_day"),
                "jump_day_t_plus_1": value_at(1, "jump_day"),
                "normal_mean_rvol": normal_mean,
                "event_window_mean_rvol": window_mean,
                "event_vs_normal_ratio": (
                    window_mean / normal_mean
                    if np.isfinite(normal_mean) and normal_mean > 0
                    else np.nan
                ),
                "normal_jump_frequency": (
                    float(normal["jump_day"].mean()) if not normal.empty else np.nan
                ),
                "event_window_jump_frequency": float(window["jump_day"].mean()),
                "status": "ok",
            }
        )
    return pd.DataFrame(rows).reindex(columns=EVENT_COLUMNS)


def _plot_event_summary(summary: pd.DataFrame, path: Path) -> None:
    plt.close("all")
    figure, axis = plt.subplots(figsize=(10, 5.5))
    valid = summary.loc[summary["status"].eq("ok")].copy()
    if valid.empty:
        axis.text(
            0.5,
            0.5,
            "Nenhum evento manual preenchido ou presente na amostra.",
            ha="center",
            va="center",
            fontsize=13,
        )
        axis.set_axis_off()
    else:
        positions = np.arange(len(valid))
        width = 0.36
        axis.bar(
            positions - width / 2,
            100 * valid["normal_mean_rvol"],
            width,
            label="Dias normais",
            color="#4C78A8",
        )
        axis.bar(
            positions + width / 2,
            100 * valid["event_window_mean_rvol"],
            width,
            label="Janela t-1 a t+1",
            color="#E45756",
        )
        axis.set_xticks(positions)
        axis.set_xticklabels(
            valid["ticker"] + "\n" + valid["event_date"].astype(str),
            rotation=30,
            ha="right",
        )
        axis.set_ylabel("Volatilidade realizada diaria (%)")
        axis.legend(frameon=False)
        axis.grid(axis="y", alpha=0.25)
    axis.set_title("Volatilidade em janelas de divulgacao de resultados")
    figure.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(figure)


def run_event_analysis(
    config: dict[str, Any] | None = None,
) -> pd.DataFrame:
    """Executa a etapa opcional sem interromper a pipeline vazia."""
    config = config or load_config()
    events_path = PROJECT_ROOT / "data" / "manual" / "events_earnings.csv"
    measures_path = PROJECT_ROOT / "data" / "processed" / "realized_measures.csv"
    events = load_manual_events(events_path)
    measures = (
        pd.read_csv(measures_path, parse_dates=["date"])
        if measures_path.exists()
        else pd.DataFrame()
    )
    summary = analyze_event_windows(events, measures)
    save_csv(
        summary,
        PROJECT_ROOT / "outputs" / "tables" / "event_window_summary.csv",
    )
    _plot_event_summary(
        summary,
        PROJECT_ROOT / "outputs" / "figures" / "event_window_volatility.png",
    )
    LOGGER.info("Eventos manuais validos analisados: %d", len(summary))
    return summary

