"""Limpeza, sincronizacao e construcao de retornos intradiarios."""

from __future__ import annotations

from datetime import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .config import PROJECT_ROOT, load_config
from .utils import save_csv, setup_logging


LOGGER = setup_logging(__name__)
PRICE_COLUMNS = ["open", "high", "low", "close"]


def _parse_market_time(value: str) -> time:
    return pd.Timestamp(value).time()


def _minutes_since_midnight(values: pd.Series) -> pd.Series:
    """Converte timestamps timezone-aware em minutos desde meia-noite."""
    return values.dt.hour * 60 + values.dt.minute


def infer_effective_market_close(
    data: pd.DataFrame,
    configured_close: str,
    min_support_share: float = 0.80,
) -> str:
    """Infere o último horário intradiário sustentado pela fonte.

    O fechamento configurado funciona como teto. O horário efetivo é o último
    minuto observado em pelo menos ``min_support_share`` dos ticker-dias, o que
    evita prolongar a grade com preços carregados quando a fonte deixa de
    fornecer candles antes do limite nominal.
    """
    if data.empty:
        return configured_close
    if not 0 < min_support_share <= 1:
        raise ValueError("min_support_share deve estar no intervalo (0, 1]")

    daily_last = (
        data.groupby(["ticker", data["datetime"].dt.date])["datetime"]
        .max()
        .reset_index(drop=True)
    )
    last_minutes = _minutes_since_midnight(daily_last)
    configured_time = _parse_market_time(configured_close)
    configured_minutes = configured_time.hour * 60 + configured_time.minute
    candidates = sorted(
        minute
        for minute in last_minutes.dropna().astype(int).unique()
        if minute <= configured_minutes
    )
    supported = [
        minute
        for minute in candidates
        if float(last_minutes.ge(minute).mean()) >= min_support_share
    ]
    if not supported:
        return configured_close

    selected = max(supported)
    return f"{selected // 60:02d}:{selected % 60:02d}"


def normalize_datetime(
    values: pd.Series,
    timezone: str,
) -> pd.Series:
    """Converte timestamps para o fuso de Sao Paulo."""
    parsed = pd.to_datetime(values, errors="coerce")
    try:
        current_tz = parsed.dt.tz
    except AttributeError:
        parsed = pd.to_datetime(values, errors="coerce", utc=True)
        current_tz = parsed.dt.tz

    if current_tz is None:
        return parsed.dt.tz_localize(
            timezone,
            ambiguous="NaT",
            nonexistent="shift_forward",
        )
    return parsed.dt.tz_convert(timezone)


def clean_price_frame(
    data: pd.DataFrame,
    timezone: str = "America/Sao_Paulo",
    market_open: str = "10:00",
    market_close: str = "17:55",
) -> pd.DataFrame:
    """Remove duplicatas, horarios irregulares e precos invalidos."""
    required = {"datetime", "ticker", *PRICE_COLUMNS, "volume"}
    missing = required.difference(data.columns)
    if missing:
        raise ValueError(f"Colunas obrigatorias ausentes: {sorted(missing)}")

    frame = data.copy()
    frame["datetime"] = normalize_datetime(frame["datetime"], timezone)
    for column in [*PRICE_COLUMNS, "volume"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    frame = frame.dropna(subset=["datetime", "ticker", *PRICE_COLUMNS])
    positive_mask = frame[PRICE_COLUMNS].gt(0).all(axis=1)
    frame = frame.loc[positive_mask].copy()
    frame["volume"] = frame["volume"].fillna(0).clip(lower=0)

    open_time = _parse_market_time(market_open)
    close_time = _parse_market_time(market_close)
    clock = frame["datetime"].dt.time
    frame = frame.loc[(clock >= open_time) & (clock <= close_time)]
    frame = frame.drop_duplicates(subset=["ticker", "datetime"], keep="last")
    return frame.sort_values(["ticker", "datetime"]).reset_index(drop=True)


def _synchronize_one_day(
    day_data: pd.DataFrame,
    timezone: str,
    market_open: str,
    market_close: str,
    interval: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    ticker = str(day_data["ticker"].iloc[0])
    date_value = day_data["datetime"].dt.date.iloc[0]
    bucketed = day_data.assign(
        datetime=day_data["datetime"].dt.floor(interval)
    ).groupby("datetime", as_index=True).agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
    )

    start = pd.Timestamp(f"{date_value} {market_open}", tz=timezone)
    end = pd.Timestamp(f"{date_value} {market_close}", tz=timezone)
    expected_index = pd.date_range(start=start, end=end, freq=interval)
    synchronized = bucketed.reindex(expected_index)
    observed = synchronized["close"].notna()

    synchronized[PRICE_COLUMNS] = synchronized[PRICE_COLUMNS].ffill()
    synchronized["volume"] = synchronized["volume"].fillna(0)
    synchronized["observed_candle"] = observed
    synchronized["ticker"] = ticker
    synchronized["date"] = date_value
    synchronized["time"] = synchronized.index.strftime("%H:%M")
    synchronized.index.name = "datetime"
    synchronized = synchronized.reset_index()
    synchronized = synchronized.dropna(subset=["close"])
    synchronized["log_return"] = np.log(synchronized["close"]).diff()

    valid_returns = synchronized["log_return"].dropna()
    stale_share = (
        float(valid_returns.eq(0).mean()) if not valid_returns.empty else np.nan
    )
    quality = {
        "ticker": ticker,
        "date": date_value,
        "expected_candles": len(expected_index),
        "observed_candles": int(observed.sum()),
        "candle_coverage": float(observed.mean()),
        "valid_intraday_returns": int(valid_returns.notna().sum()),
        "stale_price_share": stale_share,
        "positive_volume_share": float(
            synchronized.loc[synchronized["observed_candle"], "volume"].gt(0).mean()
        )
        if observed.any()
        else 0.0,
        "all_prices_positive": bool(
            synchronized[PRICE_COLUMNS].gt(0).all(axis=None)
        ),
    }
    return synchronized, quality


def synchronize_intraday(
    data: pd.DataFrame,
    timezone: str = "America/Sao_Paulo",
    market_open: str = "10:00",
    market_close: str = "17:55",
    interval: str = "5min",
    infer_market_close: bool = True,
    min_close_support_share: float = 0.80,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Sincroniza cada ticker-dia e aplica forward-fill apenas no mesmo dia."""
    clean = clean_price_frame(data, timezone, market_open, market_close)
    effective_market_close = (
        infer_effective_market_close(
            clean,
            configured_close=market_close,
            min_support_share=min_close_support_share,
        )
        if infer_market_close
        else market_close
    )
    if effective_market_close != market_close:
        LOGGER.info(
            "Fechamento efetivo inferido em %s (teto configurado: %s; suporte: %.0f%%)",
            effective_market_close,
            market_close,
            100 * min_close_support_share,
        )
    clean["date_key"] = clean["datetime"].dt.date

    synchronized_parts: list[pd.DataFrame] = []
    quality_rows: list[dict[str, Any]] = []
    for (_, _), group in clean.groupby(["ticker", "date_key"], sort=True):
        synchronized, quality = _synchronize_one_day(
            group,
            timezone=timezone,
            market_open=market_open,
            market_close=effective_market_close,
            interval=interval,
        )
        quality["configured_market_close"] = market_close
        quality["effective_market_close"] = effective_market_close
        synchronized_parts.append(synchronized)
        quality_rows.append(quality)

    columns = [
        "datetime",
        "date",
        "time",
        "ticker",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "observed_candle",
        "log_return",
    ]
    if not synchronized_parts:
        return pd.DataFrame(columns=columns), pd.DataFrame()

    synchronized_data = pd.concat(synchronized_parts, ignore_index=True)
    synchronized_data = synchronized_data[columns].sort_values(
        ["ticker", "datetime"]
    )
    return synchronized_data.reset_index(drop=True), pd.DataFrame(quality_rows)


def _raw_files(raw_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in raw_dir.glob("*_5m.csv")
        if path.name != "download_status.csv"
    )


def run_cleaning(
    config: dict[str, Any] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Le arquivos brutos, limpa, sincroniza e salva diagnosticos."""
    config = config or load_config()
    raw_dir = PROJECT_ROOT / "data" / "raw"
    files = _raw_files(raw_dir)
    if not files:
        raise FileNotFoundError("Nenhum arquivo intradiario encontrado em data/raw")

    frames: list[pd.DataFrame] = []
    for path in files:
        try:
            frame = pd.read_csv(path)
            if not frame.empty:
                frames.append(frame)
        except Exception:  # noqa: BLE001
            LOGGER.exception("Falha ao ler %s", path)

    if not frames:
        raise ValueError("Arquivos brutos existem, mas nenhum pode ser lido")

    raw = pd.concat(frames, ignore_index=True)
    settings = config["data"]
    synchronized, quality = synchronize_intraday(
        raw,
        timezone=settings["timezone"],
        market_open=settings["market_open"],
        market_close=settings["market_close"],
        interval=settings["resample_interval"],
        infer_market_close=settings.get("infer_effective_market_close", True),
        min_close_support_share=settings.get("min_close_support_share", 0.80),
    )
    interim_dir = PROJECT_ROOT / "data" / "interim"
    save_csv(synchronized, interim_dir / "intraday_synchronized.csv")
    save_csv(quality, interim_dir / "daily_data_quality.csv")

    audit = (
        raw.groupby("ticker")
        .size()
        .rename("raw_rows")
        .to_frame()
        .join(
            synchronized.groupby("ticker").size().rename("synchronized_rows"),
            how="outer",
        )
        .fillna(0)
        .reset_index()
    )
    save_csv(audit, interim_dir / "cleaning_audit.csv")
    return synchronized, quality
