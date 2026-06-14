import pandas as pd

from vol_realizada_b3.sample_selection import evaluate_sample_quality


def _config() -> dict:
    return {
        "tickers": {
            "core_liquid": ["GOOD3.SA", "BAD3.SA"],
            "high_vol_growth_candidates": [],
        },
        "sample_selection": {
            "min_valid_days": 2,
            "min_avg_candle_coverage": 0.70,
            "min_intraday_returns_per_day": 40,
            "max_stale_price_share": 0.50,
            "min_positive_volume_share": 0.10,
            "require_positive_prices": True,
        },
    }


def _quality() -> pd.DataFrame:
    rows = []
    for ticker, coverage in [("GOOD3.SA", 0.9), ("BAD3.SA", 0.4)]:
        for date in ["2026-05-04", "2026-05-05"]:
            rows.append(
                {
                    "ticker": ticker,
                    "date": date,
                    "expected_candles": 96,
                    "observed_candles": int(96 * coverage),
                    "candle_coverage": coverage,
                    "valid_intraday_returns": 80 if ticker == "GOOD3.SA" else 30,
                    "stale_price_share": 0.1,
                    "positive_volume_share": 0.8,
                    "all_prices_positive": True,
                }
            )
    return pd.DataFrame(rows)


def _synchronized() -> pd.DataFrame:
    rows = []
    for ticker in ["GOOD3.SA", "BAD3.SA"]:
        for value in [0.001, 0.0, -0.001, 0.002]:
            rows.append({"ticker": ticker, "log_return": value})
    return pd.DataFrame(rows)


def test_sample_selection_excludes_low_coverage() -> None:
    result = evaluate_sample_quality(
        _quality(), _synchronized(), _config()
    ).set_index("ticker")
    assert result.loc["BAD3.SA", "status"] == "excluded"


def test_sample_selection_keeps_valid_ticker() -> None:
    result = evaluate_sample_quality(
        _quality(), _synchronized(), _config()
    ).set_index("ticker")
    assert result.loc["GOOD3.SA", "status"] == "included"

