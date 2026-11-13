"""Run-specific, market-data-ranked research shortlist.

The service samples a broad NSE candidate pool on every assessment, then ranks usable
price histories on risk-band-specific factors. Sampling only changes discovery coverage;
it does not add random noise to the market signals themselves.
"""
from __future__ import annotations

import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

from .market_data import fetch_history, nse_symbol
from .universe_lists import BUILTIN_WATCHLISTS

UNIVERSE_PATH = Path(__file__).resolve().parents[2] / "data" / "nse_universe.json"


def _all_symbols() -> list[str]:
    symbols: list[str] = []
    try:
        source = json.loads(UNIVERSE_PATH.read_text(encoding="utf-8"))
        symbols.extend(str(value).upper() for value in source.values())
    except (OSError, ValueError, TypeError):
        pass
    for item in BUILTIN_WATCHLISTS.values():
        symbols.extend(item["symbols"])
    return list(dict.fromkeys(symbols))


def _candidate_pool(risk_category: str) -> list[str]:
    large = BUILTIN_WATCHLISTS["large_caps"]["symbols"]
    mid = BUILTIN_WATCHLISTS["mid_caps"]["symbols"]
    small = BUILTIN_WATCHLISTS["small_caps"]["symbols"]
    all_symbols = _all_symbols()
    if risk_category == "Conservative":
        preferred = large + mid[:8]
    elif risk_category == "Aggressive":
        preferred = mid + small + [s for s in all_symbols if s not in large]
    else:
        preferred = large + mid + small + all_symbols
    return list(dict.fromkeys(preferred))


def _analyse(symbol: str) -> dict | None:
    frame = fetch_history(nse_symbol(symbol), "1y", interval="1d", ttl_seconds=180)
    if frame.empty or "Close" not in frame or len(frame) < 80:
        return None
    close = frame["Close"].dropna().astype(float)
    returns = close.pct_change().dropna()
    if len(returns) < 60:
        return None
    vol20 = float(returns.tail(20).std(ddof=1) * np.sqrt(252))
    vol60 = float(returns.tail(60).std(ddof=1) * np.sqrt(252))
    mom20 = float(close.iloc[-1] / close.iloc[-21] - 1) if len(close) >= 21 else 0.0
    mom60 = float(close.iloc[-1] / close.iloc[-61] - 1) if len(close) >= 61 else 0.0
    mom120 = float(close.iloc[-1] / close.iloc[-121] - 1) if len(close) >= 121 else mom60
    peak = close.tail(252).cummax()
    drawdown = float((close.tail(252) / peak - 1).min())
    avg_volume = None
    if "Volume" in frame:
        avg_volume = float(frame["Volume"].tail(20).mean())
    return {
        "symbol": symbol,
        "momentum_20d": mom20,
        "momentum_60d": mom60,
        "momentum_120d": mom120,
        "volatility_20d": max(vol20, 0.0),
        "volatility_60d": max(vol60, 0.0),
        "max_drawdown_1y": drawdown,
        "average_volume_20d": avg_volume,
        "as_of": pd.Timestamp(close.index[-1]).strftime("%d %b %Y"),
    }


def _percentile(values: list[float], higher_is_better: bool = True) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    ranks = pd.Series(array).rank(method="average", pct=True).to_numpy()
    return ranks if higher_is_better else 1.0 - ranks


def recommend_stocks(risk_category: str, count: int | None = None, assessment_key: str | None = None) -> list[dict]:
    """Return a diverse shortlist based on current available historical data.

    Recommendations intentionally vary across assessments by using a fresh random
    candidate sample from the relevant risk universe, followed by signal-weighted
    selection from the strongest candidates. The random process never changes metrics.
    """
    if risk_category not in {"Conservative", "Moderate", "Aggressive"}:
        risk_category = "Moderate"
    count = min(max(int(count or 8), 1), 12)
    pool = _candidate_pool(risk_category)
    rng = np.random.default_rng()
    sample_size = min(len(pool), max(24, count * 3))
    sampled = list(rng.choice(pool, size=sample_size, replace=False)) if len(pool) > sample_size else pool

    with ThreadPoolExecutor(max_workers=12) as executor:
        analysed = [row for row in executor.map(_analyse, sampled) if row is not None]
    if not analysed:
        return []

    momentum = [row["momentum_60d"] for row in analysed]
    momentum_long = [row["momentum_120d"] for row in analysed]
    volatility = [row["volatility_20d"] for row in analysed]
    drawdowns = [abs(row["max_drawdown_1y"]) for row in analysed]
    liquidity = [row["average_volume_20d"] or 0.0 for row in analysed]

    mom_rank = _percentile(momentum)
    long_mom_rank = _percentile(momentum_long)
    low_vol_rank = _percentile(volatility, higher_is_better=False)
    low_dd_rank = _percentile(drawdowns, higher_is_better=False)
    liquid_rank = _percentile(liquidity)

    for index, row in enumerate(analysed):
        if risk_category == "Conservative":
            score = 0.35 * low_vol_rank[index] + 0.30 * low_dd_rank[index] + 0.20 * mom_rank[index] + 0.15 * liquid_rank[index]
            reason = "Lower realised volatility and drawdown within this candidate set"
        elif risk_category == "Aggressive":
            score = 0.38 * long_mom_rank[index] + 0.27 * mom_rank[index] + 0.15 * (1 - low_vol_rank[index]) + 0.12 * low_dd_rank[index] + 0.08 * liquid_rank[index]
            reason = "Stronger medium-term momentum; higher drawdown risk remains possible"
        else:
            score = 0.30 * mom_rank[index] + 0.20 * long_mom_rank[index] + 0.25 * low_vol_rank[index] + 0.15 * low_dd_rank[index] + 0.10 * liquid_rank[index]
            reason = "Balanced momentum, realised volatility and drawdown profile"
        row["_score"] = float(score)
        row["reason"] = reason

    analysed.sort(key=lambda item: item["_score"], reverse=True)
    # Sample from a ranked top pool rather than returning the same hard-coded symbols.
    candidate_top = analysed[: min(len(analysed), max(count * 3, count))]
    raw_scores = np.asarray([item["_score"] for item in candidate_top], dtype=float)
    weights = np.exp((raw_scores - raw_scores.max()) * 5.0)
    weights = weights / weights.sum()
    selected_indices = rng.choice(len(candidate_top), size=min(count, len(candidate_top)), replace=False, p=weights)
    selected = [candidate_top[int(i)] for i in selected_indices]
    selected.sort(key=lambda item: item["_score"], reverse=True)

    results = []
    for row in selected:
        results.append({
            "symbol": row["symbol"],
            "available": True,
            "reason": row["reason"],
            "momentum_20d_pct": round(row["momentum_20d"] * 100, 2),
            "momentum_60d_pct": round(row["momentum_60d"] * 100, 2),
            "volatility_20d_pct": round(row["volatility_20d"] * 100, 2),
            "max_drawdown_1y_pct": round(row["max_drawdown_1y"] * 100, 2),
            "as_of": row["as_of"],
        })
    return results
