"""Curated NSE watchlist starters, refreshed against published index/market lists.

The lists are starting universes, not rankings computed from live market cap. Mid/small
lists use index constituent weights to define a reproducible short list.
"""
from __future__ import annotations

BUILTIN_WATCHLISTS = {
    "large_caps": {
        "name": "Large Caps · Top 15",
        "subtitle": "Large, actively traded NSE companies",
        "as_of": "13 Nov 2026",
        "basis": "Market-cap leaders from current public NSE market-cap lists",
        "symbols": [
            "RELIANCE", "BHARTIARTL", "HDFCBANK", "ICICIBANK", "SBIN",
            "TCS", "BAJFINANCE", "LT", "LICI", "HINDUNILVR", "INFY",
            "ITC", "MARUTI", "KOTAKBANK", "SUNPHARMA",
        ],
    },
    "mid_caps": {
        "name": "Mid Caps · Top 20",
        "subtitle": "Nifty Midcap 150 leading index weights",
        "as_of": "30 Sep 2026",
        "basis": "Top constituent weights in the Nifty Midcap 150 index-fund portfolio",
        "symbols": [
            "MCX", "FEDERALBNK", "LAURUSLABS", "PAYTM", "HEROMOTOCO",
            "INDHOTEL", "COFORGE", "BHEL", "INDUSINDBK", "AUBANK",
            "PERSISTENT", "DIXON", "IDFCFIRSTB", "BHARATFORG", "GVT&D",
            "LICI", "LENSKART", "LUPIN", "SUZLON", "INDUSTOWER",
        ],
    },
    "small_caps": {
        "name": "Small Caps · Top 10",
        "subtitle": "Nifty Smallcap 250 leading index weights",
        "as_of": "30 Sep 2026",
        "basis": "Top holdings reported by a Nifty Smallcap 250 index fund; not a market-cap ranking",
        "symbols": [
            "SONACOMS", "WELCORP", "KARURVYSYA", "NAVINFLUOR", "ATHERENERG",
            "RBLBANK", "REDINGTON", "DELHIVERY", "HFCL", "GLAND",
        ],
    },
}

RISK_CANDIDATES = {
    "Conservative": BUILTIN_WATCHLISTS["large_caps"]["symbols"],
    "Moderate": BUILTIN_WATCHLISTS["large_caps"]["symbols"] + BUILTIN_WATCHLISTS["mid_caps"]["symbols"][:12],
    "Aggressive": BUILTIN_WATCHLISTS["mid_caps"]["symbols"] + BUILTIN_WATCHLISTS["small_caps"]["symbols"],
}
