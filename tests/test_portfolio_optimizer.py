import numpy as np
import pandas as pd
import pytest
from app.services import portfolio_optimizer as optimiser


def test_symbol_validation_deduplicates_and_normalises():
    assert optimiser._clean_symbols("reliance, HDFCBANK.NS, infy, tcs, itc, RELIANCE") == [
        "RELIANCE", "HDFCBANK", "INFY", "TCS", "ITC"
    ]


def test_symbol_validation_requires_four_symbols():
    with pytest.raises(ValueError):
        optimiser._clean_symbols("RELIANCE,TCS,INFY")


def test_cvar_optimiser_respects_constraints(monkeypatch):
    rng = np.random.default_rng(19)
    dates = pd.bdate_range("2022-01-01", periods=420)
    returns = rng.normal(0.00025, 0.011, size=(420, 4))
    returns[:, 1] = 0.5 * returns[:, 0] + rng.normal(0.0001, 0.008, size=420)
    symbols = ["AAA", "BBB", "CCC", "DDD"]
    frames = {
        symbol: pd.DataFrame({"Close": 100 * np.cumprod(1 + returns[:, idx])}, index=dates)
        for idx, symbol in enumerate(symbols)
    }
    monkeypatch.setattr(
        optimiser, "fetch_history",
        lambda ticker, period, ttl_seconds=900: frames[ticker.replace(".NS", "")],
    )
    output = optimiser.optimize_portfolio(",".join(symbols), "Moderate")
    weights = [item["weight"] for item in output["allocations"]]
    assert len(weights) == 4
    assert abs(sum(weights) - 1.0) < 1e-7
    assert min(weights) >= 0
    assert max(weights) <= 0.400001
