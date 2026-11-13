"""Market-data adapters with bounded caching, retries and explicit data freshness.

Yahoo Finance is a convenient research source, not an exchange-grade feed. Values are
always accompanied by source/as-of metadata so the UI can distinguish intraday snapshots
from the last completed daily close.
"""
from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, time as clock_time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

_cache: dict[tuple[str, str, str], tuple[float, pd.DataFrame]] = {}
_quote_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_cache_lock = threading.RLock()
INDIA_TZ = ZoneInfo("Asia/Kolkata")
PRE_OPEN_START = clock_time(9, 0)
MARKET_OPEN = clock_time(9, 15)
MARKET_CLOSE = clock_time(15, 30)
HOLIDAY_FILE = Path(__file__).resolve().parents[2] / "data" / "nse_holidays.json"


def _holiday_dates() -> set[date]:
    """Load NSE cash-market holidays maintained in data/nse_holidays.json."""
    try:
        payload = json.loads(HOLIDAY_FILE.read_text(encoding="utf-8"))
        return {date.fromisoformat(value) for value in payload.get("holidays", [])}
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return set()


def _is_trading_day(day: date, holidays: set[date]) -> bool:
    return day.weekday() < 5 and day not in holidays


def _next_trading_day(day: date, holidays: set[date]) -> date:
    candidate = day
    for _ in range(15):
        candidate += timedelta(days=1)
        if _is_trading_day(candidate, holidays):
            return candidate
    # Defensive fallback: the next weekday, even if a stale holiday file is malformed.
    while candidate.weekday() >= 5:
        candidate += timedelta(days=1)
    return candidate


def fetch_history(
    symbol: str,
    period: str = "3y",
    interval: str = "1d",
    ttl_seconds: int = 900,
    allow_stale: bool = True,
) -> pd.DataFrame:
    """Fetch adjusted OHLCV, retry transient errors and preserve last-good cache.

    The cache key includes interval. On provider failure, a previously cached frame is
    returned rather than replacing valid history with an empty frame.
    """
    key = (symbol.upper().strip(), period, interval)
    now = time.monotonic()
    with _cache_lock:
        cached = _cache.get(key)
        if cached and now - cached[0] < ttl_seconds:
            return cached[1].copy()
        stale = cached[1].copy() if cached and allow_stale else pd.DataFrame()

    frame = pd.DataFrame()
    for attempt in range(2):
        try:
            import yfinance as yf
            downloaded = yf.download(
                key[0], period=period, interval=interval, auto_adjust=True,
                progress=False, threads=False, timeout=15,
                group_by="column", prepost=False,
            )
            if isinstance(downloaded.columns, pd.MultiIndex):
                downloaded.columns = downloaded.columns.get_level_values(0)
            if not downloaded.empty and "Close" in downloaded.columns:
                downloaded = downloaded.rename_axis("Date")
                downloaded = downloaded.dropna(subset=["Close"])
                downloaded = downloaded.loc[~downloaded.index.duplicated(keep="last")].sort_index()
                frame = downloaded
                break
        except Exception:
            if attempt == 0:
                time.sleep(0.35)

    if not frame.empty:
        with _cache_lock:
            _cache[key] = (time.monotonic(), frame.copy())
        return frame
    return stale


def nse_symbol(symbol: str) -> str:
    clean = symbol.strip().upper()
    return clean if clean.endswith(".NS") or clean.startswith("^") or "=" in clean else f"{clean}.NS"


def _number(value: Any) -> float | None:
    try:
        number = float(value)
        return number if pd.notna(number) and number > 0 else None
    except (TypeError, ValueError):
        return None


def quote_for_symbol(symbol: str, display_name: str | None = None) -> dict[str, Any]:
    """Return a fresh quote snapshot or an explicitly labelled last close."""
    clean = symbol.upper().strip()
    now_mono = time.monotonic()
    with _cache_lock:
        cached = _quote_cache.get(clean)
        if cached and now_mono - cached[0] < 30:
            result = dict(cached[1])
            if display_name:
                result["name"] = display_name
            return result

    ticker = nse_symbol(clean)
    price = previous = day_high = day_low = volume = market_cap = None
    source = None
    as_of = None
    now = datetime.now(INDIA_TZ)
    clock = market_clock()
    is_nse_equity = ticker.endswith(".NS") or ticker.startswith("^")

    # For NSE equities, prefer the last completed close outside regular market hours.
    # Fast fields are used during the session; non-NSE instruments can use them independently.
    if not is_nse_equity or clock["status"] == "OPEN":
        try:
            import yfinance as yf
            info = yf.Ticker(ticker).fast_info
            price = _number(info.get("last_price"))
            previous = _number(info.get("previous_close"))
            day_high = _number(info.get("day_high"))
            day_low = _number(info.get("day_low"))
            volume = _number(info.get("last_volume"))
            market_cap = _number(info.get("market_cap"))
            if price:
                source = "Yahoo Finance fast quote"
                as_of = now.strftime("%d %b %Y, %H:%M IST")
        except Exception:
            pass

    # Intraday bars are requested only while the regular NSE cash session is active.
    if price is None and clock["status"] == "OPEN":
        try:
            intraday = fetch_history(ticker, "1d", interval="5m", ttl_seconds=25)
            if not intraday.empty and "Close" in intraday:
                price = _number(intraday["Close"].iloc[-1])
                previous = previous or _number(intraday["Close"].iloc[0])
                day_high = _number(intraday["High"].max()) if "High" in intraday else None
                day_low = _number(intraday["Low"].min()) if "Low" in intraday else None
                volume = _number(intraday["Volume"].sum()) if "Volume" in intraday else None
                source = "Yahoo Finance 5-minute bars"
                as_of = pd.Timestamp(intraday.index[-1]).strftime("%d %b %Y, %H:%M")
        except Exception:
            pass

    daily = fetch_history(ticker, "1mo", interval="1d", ttl_seconds=90)
    if daily.empty or "Close" not in daily or len(daily) < 2:
        change = ((price / previous) - 1) * 100 if price and previous else None
        result = {
            "symbol": clean, "name": display_name or clean, "price": price,
            "change_pct": change, "previous_close": previous,
            "available": price is not None,
            "source": source or "Yahoo Finance", "as_of": as_of,
            "stale": price is None, "market_cap": market_cap,
        }
    else:
        if price is None:
            price = _number(daily["Close"].iloc[-1])
            source = "Yahoo Finance daily close"
            as_of = daily.index[-1].strftime("%d %b %Y")
        if previous is None:
            previous = _number(daily["Close"].iloc[-2])
        if day_high is None and "High" in daily:
            day_high = _number(daily["High"].iloc[-1])
        if day_low is None and "Low" in daily:
            day_low = _number(daily["Low"].iloc[-1])
        change = ((price / previous) - 1) * 100 if price and previous else None
        result = {
            "symbol": clean, "name": display_name or clean, "price": price,
            "change_pct": change, "previous_close": previous,
            "day_high": day_high, "day_low": day_low, "volume": volume,
            "market_cap": market_cap, "available": price is not None,
            "source": source or "Yahoo Finance daily close", "as_of": as_of or daily.index[-1].strftime("%d %b %Y"),
            "stale": "daily close" in (source or "").lower(),
        }
    with _cache_lock:
        _quote_cache[clean] = (time.monotonic(), dict(result))
    return result


def market_snapshot() -> list[dict[str, Any]]:
    instruments = [("NIFTY 50", "^NSEI"), ("SENSEX", "^BSESN"),
                   ("NIFTY BANK", "^NSEBANK"), ("USD / INR", "INR=X")]
    def load(item: tuple[str, str]) -> dict[str, Any]:
        name, symbol = item
        quote = quote_for_symbol(symbol, name)
        quote["price_display"] = (
            f"₹{quote['price']:,.2f}" if quote.get("available") and name == "USD / INR"
            else f"{quote['price']:,.2f}" if quote.get("available") else "—"
        )
        return quote
    with ThreadPoolExecutor(max_workers=4) as pool:
        return list(pool.map(load, instruments))


def quotes_for_symbols(symbols: list[str], names: list[str] | None = None) -> list[dict[str, Any]]:
    pairs = list(zip(symbols, names or [None] * len(symbols)))
    if not pairs:
        return []
    with ThreadPoolExecutor(max_workers=min(8, len(pairs))) as pool:
        return list(pool.map(lambda pair: quote_for_symbol(pair[0], pair[1]), pairs))


def index_series(symbol: str = "^NSEI", period: str = "1y") -> dict[str, list] | None:
    allowed = {"1mo", "3mo", "6mo", "1y", "3y", "5y"}
    if period not in allowed:
        period = "1y"
    data = fetch_history(symbol, period, interval="1d", ttl_seconds=600)
    if data.empty or not {"Open", "High", "Low", "Close"}.issubset(data.columns):
        return None
    sample = data.tail(1260)
    return {
        "dates": [pd.Timestamp(d).strftime("%Y-%m-%d") for d in sample.index],
        "labels": [pd.Timestamp(d).strftime("%d %b") for d in sample.index],
        "open": [round(float(v), 2) for v in sample["Open"].tolist()],
        "high": [round(float(v), 2) for v in sample["High"].tolist()],
        "low": [round(float(v), 2) for v in sample["Low"].tolist()],
        "close": [round(float(v), 2) for v in sample["Close"].tolist()],
        "values": [round(float(v), 2) for v in sample["Close"].tolist()],
        "as_of": pd.Timestamp(sample.index[-1]).strftime("%d %b %Y"),
    }


def market_clock() -> dict[str, Any]:
    """NSE cash-session clock, holiday-aware when the local holiday file is populated."""
    now = datetime.now(INDIA_TZ)
    today = now.date()
    holidays = _holiday_dates()
    opens_at = datetime.combine(today, MARKET_OPEN, tzinfo=INDIA_TZ)
    closes_at = datetime.combine(today, MARKET_CLOSE, tzinfo=INDIA_TZ)
    is_trading_day = _is_trading_day(today, holidays)

    pre_open_at = datetime.combine(today, PRE_OPEN_START, tzinfo=INDIA_TZ)
    if is_trading_day and opens_at <= now < closes_at:
        status, event_label, next_event = "OPEN", "Closes", closes_at
    elif is_trading_day and pre_open_at <= now < opens_at:
        status, event_label, next_event = "PRE-OPEN", "Regular open", opens_at
    elif is_trading_day and now < pre_open_at:
        status, event_label, next_event = "CLOSED", "Pre-open", pre_open_at
    else:
        status = "CLOSED"
        next_day = _next_trading_day(today, holidays)
        next_event = datetime.combine(next_day, PRE_OPEN_START, tzinfo=INDIA_TZ)
        event_label = "Next pre-open"

    return {
        "now": now.isoformat(),
        "now_display": now.strftime("%a, %d %b · %H:%M:%S IST"),
        "status": status,
        "event_label": event_label,
        "event_at": next_event.isoformat(),
        "event_display": next_event.strftime("%d %b · %H:%M IST"),
        "pre_open_hours": "09:00–09:08 IST",
        "hours": "09:15–15:30 IST",
        "timezone": "Asia/Kolkata",
        "holiday_calendar_loaded": bool(holidays),
    }
