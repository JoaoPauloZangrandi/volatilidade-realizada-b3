import numpy as np
import pandas as pd

from vol_realizada_b3.data_cleaning import (
    clean_price_frame,
    infer_effective_market_close,
    synchronize_intraday,
)


def _row(datetime: str, close: float) -> dict[str, object]:
    return {
        "datetime": datetime,
        "ticker": "TEST3.SA",
        "open": close,
        "high": close,
        "low": close,
        "close": close,
        "volume": 100,
    }


def test_no_cross_day_returns() -> None:
    data = pd.DataFrame(
        [
            _row("2026-05-04 10:00", 10.0),
            _row("2026-05-04 10:05", 10.1),
            _row("2026-05-05 10:00", 11.0),
            _row("2026-05-05 10:05", 11.1),
        ]
    )
    synchronized, _ = synchronize_intraday(
        data,
        market_open="10:00",
        market_close="10:05",
    )
    first_returns = synchronized.groupby("date")["log_return"].nth(0)
    assert first_returns.isna().all()
    assert synchronized["log_return"].notna().sum() == 2


def test_cleaning_no_negative_prices() -> None:
    data = pd.DataFrame(
        [
            _row("2026-05-04 10:00", 10.0),
            _row("2026-05-04 10:05", -1.0),
            _row("2026-05-04 10:10", np.nan),
        ]
    )
    cleaned = clean_price_frame(data)
    assert len(cleaned) == 1
    assert cleaned["close"].gt(0).all()


def test_effective_close_avoids_artificial_tail() -> None:
    data = pd.DataFrame(
        [
            _row("2026-05-04 10:00", 10.0),
            _row("2026-05-04 10:05", 10.1),
            _row("2026-05-05 10:00", 11.0),
            _row("2026-05-05 10:05", 11.1),
        ]
    )
    clean = clean_price_frame(data, market_close="10:30")
    assert infer_effective_market_close(clean, "10:30") == "10:05"

    synchronized, quality = synchronize_intraday(
        data,
        market_open="10:00",
        market_close="10:30",
    )
    assert synchronized["time"].max() == "10:05"
    assert quality["effective_market_close"].eq("10:05").all()
    assert quality["expected_candles"].eq(2).all()
