"""Yahoo's incomplete current-day rows must not become price observations."""
import pandas as pd
import pytest
from openbb_core.provider.utils.errors import EmptyDataError
from openbq_yfinance.models.prices import HistoricalFetcher


@pytest.mark.parametrize("interval", ["1d", "1h"])
def test_missing_close_is_not_a_bar_and_valid_zero_close_is_preserved(interval):
    query = HistoricalFetcher.transform_query({"symbol": "AAPL", "interval": interval})
    frame = pd.DataFrame({"Open": [1., None, 0.], "High": [2., None, 0.],
                          "Low": [0., None, 0.], "Close": [1., None, 0.], "Volume": [10, 0, 0]},
                         index=pd.date_range("2026-01-02", periods=3, tz="America/New_York"))
    rows = HistoricalFetcher.transform_data(query, {"AAPL": frame})
    assert len(rows) == 2
    assert [row.close for row in rows] == [1., 0.]
    assert str(rows[0].date).startswith("2026-01-02")
    assert str(rows[1].date).startswith("2026-01-04")


def test_placeholder_only_history_reports_empty_instead_of_validation_error():
    query = HistoricalFetcher.transform_query({"symbol": "AAPL"})
    frame = pd.DataFrame({"Close": [float("nan")]}, index=pd.date_range("2026-01-02", periods=1))
    with pytest.raises(EmptyDataError):
        HistoricalFetcher.transform_data(query, {"AAPL": frame})
