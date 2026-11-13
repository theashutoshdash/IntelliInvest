import numpy as np
import pandas as pd
from app.services import return_forecaster as forecaster


def test_walk_forward_forecast_runs_without_future_leakage(monkeypatch):
    rng = np.random.default_rng(21)
    daily = rng.normal(0.0002, 0.012, 900)
    close = 100 * np.cumprod(1 + daily)
    frame = pd.DataFrame({"Close": close}, index=pd.bdate_range("2021-01-01", periods=900))
    monkeypatch.setattr(forecaster, "fetch_history", lambda *args, **kwargs: frame)
    result = forecaster.forecast_return("TEST", "3y")
    assert result["horizon_days"] == 5
    assert result["backtest_observations"] > 30
    assert isinstance(result["model_has_edge"], bool)
    assert len(result["chart"]["labels"]) == len(result["chart"]["actual"])
    assert len(result["chart"]["labels"]) == len(result["chart"]["predicted"])
