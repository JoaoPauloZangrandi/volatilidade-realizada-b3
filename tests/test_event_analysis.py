import pandas as pd

from vol_realizada_b3.event_analysis import (
    analyze_event_windows,
    load_manual_events,
)


def test_event_analysis_empty_file_does_not_break_pipeline(tmp_path) -> None:
    path = tmp_path / "events_earnings.csv"
    path.write_text(
        "ticker,date,event_type,event_description\n",
        encoding="utf-8",
    )
    events = load_manual_events(path)
    result = analyze_event_windows(events, pd.DataFrame())
    assert events.empty
    assert result.empty
    assert "status" in result.columns
