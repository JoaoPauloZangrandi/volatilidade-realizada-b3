"""Download de dados intradiarios da B3 via yfinance."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from .config import PROJECT_ROOT, configured_tickers, load_config
from .utils import save_csv, setup_logging, ticker_slug


LOGGER = setup_logging(__name__)
STANDARD_COLUMNS = [
    "datetime",
    "ticker",
    "open",
    "high",
    "low",
    "close",
    "volume",
]


def _normalize_yfinance_frame(data: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Padroniza a resposta do yfinance para formato longo."""
    if data.empty:
        return pd.DataFrame(columns=STANDARD_COLUMNS)

    frame = data.copy()
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = [
            str(column[0] if column[0] else column[-1]).lower()
            for column in frame.columns
        ]
    else:
        frame.columns = [str(column).lower().replace(" ", "_") for column in frame.columns]

    index_name = frame.index.name or "datetime"
    frame = frame.reset_index().rename(columns={index_name: "datetime"})
    if "datetime" not in frame.columns:
        frame = frame.rename(columns={frame.columns[0]: "datetime"})

    rename_map = {
        "adj_close": "adj_close",
        "adj close": "adj_close",
    }
    frame = frame.rename(columns=rename_map)
    required = ["open", "high", "low", "close", "volume"]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"Colunas ausentes para {ticker}: {missing}")

    frame["ticker"] = ticker
    frame["datetime"] = pd.to_datetime(frame["datetime"], errors="coerce")
    frame = frame.dropna(subset=["datetime"])
    return frame[STANDARD_COLUMNS].sort_values("datetime").reset_index(drop=True)


def download_ticker(
    ticker: str,
    period: str,
    interval: str,
) -> pd.DataFrame:
    """Baixa um ticker e devolve o esquema padronizado."""
    import yfinance as yf

    data = yf.download(
        ticker,
        period=period,
        interval=interval,
        auto_adjust=False,
        actions=False,
        prepost=False,
        progress=False,
        threads=False,
        timeout=30,
    )
    return _normalize_yfinance_frame(data, ticker)


def run_download(
    config: dict[str, Any] | None = None,
    force: bool = False,
) -> pd.DataFrame:
    """Baixa todos os candidatos, registra falhas e continua."""
    config = config or load_config()
    raw_dir = PROJECT_ROOT / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    period = config["data"]["period"]
    interval = config["data"]["interval"]
    status_rows: list[dict[str, Any]] = []

    for ticker in configured_tickers(config):
        output_path = raw_dir / f"{ticker_slug(ticker)}_{interval}.csv"
        try:
            if output_path.exists() and not force:
                frame = pd.read_csv(output_path)
                source_status = "existing_file"
            else:
                LOGGER.info("Baixando %s (%s, %s)", ticker, period, interval)
                frame = download_ticker(ticker, period, interval)
                if frame.empty:
                    raise ValueError("download vazio")
                save_csv(frame, output_path)
                source_status = "downloaded"

            datetimes = pd.to_datetime(frame["datetime"], errors="coerce")
            status_rows.append(
                {
                    "ticker": ticker,
                    "status": "available",
                    "source_status": source_status,
                    "rows": len(frame),
                    "first_datetime": datetimes.min(),
                    "last_datetime": datetimes.max(),
                    "error": "",
                    "raw_file": str(output_path.relative_to(PROJECT_ROOT)),
                }
            )
        except Exception as exc:  # noqa: BLE001 - a pipeline deve continuar
            LOGGER.exception("Falha no download de %s", ticker)
            status_rows.append(
                {
                    "ticker": ticker,
                    "status": "unavailable",
                    "source_status": "download_failed",
                    "rows": 0,
                    "first_datetime": pd.NaT,
                    "last_datetime": pd.NaT,
                    "error": str(exc),
                    "raw_file": "",
                }
            )

    status = pd.DataFrame(status_rows)
    save_csv(status, raw_dir / "download_status.csv")
    return status

