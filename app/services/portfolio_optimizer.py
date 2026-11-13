from __future__ import annotations
import re
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import pandas as pd
from scipy.optimize import linprog
from .market_data import fetch_history, nse_symbol

RISK_SETTINGS = {
    "Conservative": {"tail_confidence": 0.975, "max_weight": 0.35, "label": "Capital preservation"},
    "Moderate": {"tail_confidence": 0.95, "max_weight": 0.40, "label": "Balanced risk"},
    "Aggressive": {"tail_confidence": 0.90, "max_weight": 0.50, "label": "Higher volatility tolerance"},
}

STRATEGIC_ALLOCATIONS = {
    "Conservative": {"Equity": 25, "High-quality debt": 55, "Gold": 15, "Cash": 5},
    "Moderate": {"Equity": 55, "High-quality debt": 30, "Gold": 10, "Cash": 5},
    "Aggressive": {"Equity": 75, "High-quality debt": 15, "Gold": 7, "Cash": 3},
}


def _clean_symbols(raw_symbols) -> list[str]:
    if isinstance(raw_symbols, str):
        items = re.split(r"[,;\s]+", raw_symbols)
    else:
        items = raw_symbols or []
    symbols = []
    for item in items:
        clean = str(item).strip().upper()
        if not clean:
            continue
        if clean.endswith(".NS"):
            clean = clean[:-3]
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9&_-]{0,19}", clean):
            raise ValueError(f"'{clean}' is not a supported NSE ticker format.")
        if clean not in symbols:
            symbols.append(clean)
    if not 4 <= len(symbols) <= 12:
        raise ValueError("Enter between 4 and 12 distinct NSE symbols.")
    return symbols


def optimize_portfolio(raw_symbols, risk_category: str, period: str = "3y") -> dict:
    """Long-only historical CVaR optimisation with a per-position concentration cap."""
    if risk_category not in RISK_SETTINGS:
        risk_category = "Moderate"
    symbols = _clean_symbols(raw_symbols)
    histories = {}
    missing = []
    def load(symbol):
        return symbol, fetch_history(nse_symbol(symbol), period, ttl_seconds=900)

    with ThreadPoolExecutor(max_workers=6) as pool:
        fetched = list(pool.map(load, symbols))
    for symbol, frame in fetched:
        if frame.empty or "Close" not in frame or frame["Close"].dropna().shape[0] < 180:
            missing.append(symbol)
            continue
        histories[symbol] = frame["Close"].rename(symbol)
    if len(histories) < 4:
        raise ValueError(
            "At least four symbols need 180 or more daily observations. Check the NSE ticker spellings and market-data availability."
        )

    prices = pd.concat(histories.values(), axis=1).sort_index()
    returns = prices.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)
    returns = returns.dropna(how="any")
    if len(returns) < 180:
        raise ValueError("Not enough overlapping daily history to estimate portfolio tail risk.")

    settings = RISK_SETTINGS[risk_category]
    n_assets = len(histories)
    n_days = len(returns)
    tail_fraction = 1.0 - settings["tail_confidence"]
    max_weight = max(settings["max_weight"], 1.0 / n_assets)
    max_weight = min(max_weight, 1.0)

    matrix = returns.to_numpy(dtype=float)
    # Variables: asset weights, VaR threshold (alpha), and one tail slack per day.
    objective = np.concatenate([
        np.zeros(n_assets),
        np.array([1.0]),
        np.full(n_days, 1.0 / (tail_fraction * n_days)),
    ])
    A_ub = np.zeros((n_days, n_assets + 1 + n_days), dtype=float)
    A_ub[:, :n_assets] = -matrix
    A_ub[:, n_assets] = -1.0
    A_ub[np.arange(n_days), n_assets + 1 + np.arange(n_days)] = -1.0
    b_ub = np.zeros(n_days)

    A_eq = np.zeros((1, n_assets + 1 + n_days), dtype=float)
    A_eq[0, :n_assets] = 1.0
    b_eq = np.array([1.0])
    bounds = [(0.0, max_weight)] * n_assets + [(None, None)] + [(0.0, None)] * n_days

    solved = linprog(
        objective, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq,
        bounds=bounds, method="highs",
    )
    if not solved.success:
        raise ValueError(f"Portfolio optimiser could not find a feasible solution: {solved.message}")

    weights = np.clip(solved.x[:n_assets], 0, 1)
    weights = weights / weights.sum()
    portfolio_returns = matrix @ weights
    mean_daily = float(np.mean(portfolio_returns))
    # Geometric annualisation of the daily rebalanced portfolio return series.
    annual_return = float(np.exp(np.mean(np.log(np.clip(1.0 + portfolio_returns, 1e-9, None))) * 252) - 1)
    annual_volatility = float(np.std(portfolio_returns, ddof=1) * np.sqrt(252))
    losses = -portfolio_returns
    historical_var = float(np.quantile(losses, settings["tail_confidence"]))
    historical_cvar = float(
        historical_var + np.mean(np.maximum(losses - historical_var, 0.0)) / tail_fraction
    )

    allocations = [
        {"symbol": symbol, "weight": float(weight), "weight_pct": round(float(weight) * 100, 2)}
        for symbol, weight in sorted(zip(histories.keys(), weights), key=lambda pair: pair[1], reverse=True)
    ]
    return {
        "risk_category": risk_category,
        "method": "Long-only historical CVaR minimisation (linear programme)",
        "allocations": allocations,
        "observations": int(n_days),
        "history_period": period,
        "tail_confidence": settings["tail_confidence"],
        "historical_cvar": historical_cvar,
        "historical_var": historical_var,
        "historical_tail_loss": historical_cvar,
        "annualised_historical_return": float(annual_return),
        "annualised_volatility": annual_volatility,
        "excluded_symbols": missing,
        "disclaimer": "Weights minimise historical tail loss subject to the stated concentration cap. Historical estimates are not forecasts; the optimisation is sensitive to the sample window and does not account for taxes, fees, liquidity constraints or your full financial circumstances.",
    }
