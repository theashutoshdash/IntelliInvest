from __future__ import annotations
import re
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import TimeSeriesSplit
from .market_data import fetch_history, nse_symbol

HORIZON_DAYS = 5


def _feature_frame(close: pd.Series) -> pd.DataFrame:
    close = close.astype(float)
    daily = close.pct_change(fill_method=None)
    frame = pd.DataFrame(index=close.index)
    for window in (1, 2, 5, 10, 20):
        frame[f"return_{window}d"] = close.pct_change(window, fill_method=None)
    frame["volatility_10d"] = daily.rolling(10).std() * np.sqrt(252)
    frame["volatility_20d"] = daily.rolling(20).std() * np.sqrt(252)
    frame["sma20_gap"] = close / close.rolling(20).mean() - 1
    frame["sma50_gap"] = close / close.rolling(50).mean() - 1
    frame["sma100_gap"] = close / close.rolling(100).mean() - 1
    delta = close.diff()
    gains = delta.clip(lower=0).rolling(14).mean()
    losses = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gains / losses.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    # RSI is 100/0 when one side has had no movement; a flat window is neutral.
    rsi = rsi.mask((losses == 0) & (gains > 0), 100.0)
    rsi = rsi.mask((gains == 0) & (losses > 0), 0.0)
    rsi = rsi.mask((gains == 0) & (losses == 0), 50.0)
    frame["rsi14"] = rsi
    frame["range_20d"] = (close.rolling(20).max() - close.rolling(20).min()) / close
    return frame.replace([np.inf, -np.inf], np.nan)


def _model() -> HistGradientBoostingRegressor:
    return HistGradientBoostingRegressor(
        loss="squared_error", learning_rate=0.04, max_iter=220,
        max_leaf_nodes=7, min_samples_leaf=25, l2_regularization=2.0,
        random_state=42,
    )


def forecast_return(raw_symbol: str, period: str = "3y") -> dict:
    symbol = raw_symbol.strip().upper()
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9&_-]{0,19}", symbol):
        raise ValueError("Enter a valid NSE ticker symbol, such as RELIANCE or HDFCBANK.")
    if period not in {"2y", "3y", "5y", "max"}:
        raise ValueError("Choose a supported history window.")
    ticker = nse_symbol(symbol)
    history = fetch_history(ticker, period, ttl_seconds=900)
    if history.empty or "Close" not in history:
        raise ValueError(f"No price history is available for {symbol}. Check the NSE symbol or try again later.")
    close = history["Close"].dropna()
    features = _feature_frame(close)
    target = close.shift(-HORIZON_DAYS) / close - 1.0
    supervised = features.join(target.rename("target")).dropna()
    if len(supervised) < 320:
        raise ValueError("At least 320 clean daily observations are required for a meaningful walk-forward evaluation. Use a longer history window.")

    X = supervised.drop(columns="target")
    y = supervised["target"]
    split = int(len(supervised) * 0.80)
    # Purge five rows so training targets cannot reach into the holdout period.
    train_end = split - HORIZON_DAYS
    X_train, X_test = X.iloc[:train_end], X.iloc[split:]
    y_train, y_test = y.iloc[:train_end], y.iloc[split:]
    if len(X_test) < 30:
        raise ValueError("The selected history window leaves too few observations for a holdout backtest.")

    cv_scores = []
    tscv = TimeSeriesSplit(n_splits=5, gap=HORIZON_DAYS)
    for train_idx, validation_idx in tscv.split(X_train):
        candidate = _model().fit(X_train.iloc[train_idx], y_train.iloc[train_idx])
        cv_scores.append(mean_absolute_error(
            y_train.iloc[validation_idx], candidate.predict(X_train.iloc[validation_idx])
        ))

    model = _model().fit(X_train, y_train)
    test_pred = model.predict(X_test)
    model_mae = float(mean_absolute_error(y_test, test_pred))
    zero_baseline_mae = float(mean_absolute_error(y_test, np.zeros(len(y_test))))
    direction_actual = np.sign(y_test.to_numpy())
    direction_pred = np.sign(test_pred)
    directional_accuracy = float(np.mean(direction_actual == direction_pred))
    residuals = y_test.to_numpy() - test_pred
    residual_radius = float(np.quantile(np.abs(residuals), 0.90))
    latest_features = features.dropna().iloc[[-1]]
    latest_prediction = float(model.predict(latest_features)[0])
    latest_date = close.index[-1]
    has_edge = model_mae < zero_baseline_mae

    chart_count = min(100, len(y_test))
    return {
        "symbol": symbol,
        "ticker": ticker,
        "latest_price": float(close.iloc[-1]),
        "as_of": latest_date.strftime("%d %b %Y"),
        "horizon_days": HORIZON_DAYS,
        "forecast_return": latest_prediction,
        "forecast_low": latest_prediction - residual_radius,
        "forecast_high": latest_prediction + residual_radius,
        "holdout_mae": model_mae,
        "zero_baseline_mae": zero_baseline_mae,
        "walk_forward_cv_mae": float(np.mean(cv_scores)),
        "directional_accuracy": directional_accuracy,
        "backtest_observations": int(len(y_test)),
        "model_has_edge": bool(has_edge),
        "signal_status": "Beat the zero-return benchmark on this holdout" if has_edge else "No demonstrated edge over a zero-return benchmark",
        "chart": {
            "labels": [d.strftime("%d %b %y") for d in y_test.index[-chart_count:]],
            "actual": [round(float(v) * 100, 3) for v in y_test.iloc[-chart_count:].tolist()],
            "predicted": [round(float(v) * 100, 3) for v in test_pred[-chart_count:]],
        },
        "disclaimer": "This is a five-trading-day statistical estimate, not a price target or buy/sell signal. The range is derived from absolute errors on a chronological holdout and is not a guarantee or a formal prediction interval.",
    }
