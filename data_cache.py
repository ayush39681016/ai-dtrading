"""
data_cache.py — Offline Historical Data Cache
Downloads and stores kline data locally so re-optimization
runs instantly from disk without needing live API calls.
"""

import os
import json
import time
import requests
import pandas as pd

CACHE_DIR = os.path.join(os.path.dirname(__file__), "data_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

SYMBOLS = ["BTCUSDT", "XAUUSDT", "XAGUSDT"]
INTERVALS = {"60": "1h", "15": "15m", "1": "1m"}


def _cache_path(symbol, interval):
    return os.path.join(CACHE_DIR, f"{symbol}_{interval}.csv")


def download_and_cache(symbol="BTCUSDT", interval="60", limit=1000):
    """Download klines from Bybit and save to local CSV cache."""
    url = (
        f"https://api.bybit.com/v5/market/kline"
        f"?category=linear&symbol={symbol}&interval={interval}&limit={limit}"
    )
    res = requests.get(url).json()

    if res.get("retCode") != 0:
        print(f"[!] API Error for {symbol}: {res.get('retMsg')}")
        return None

    klines = res["result"]["list"]
    klines.reverse()

    df = pd.DataFrame(klines, columns=[
        "time", "open", "high", "low", "close", "volume", "turnover"
    ])
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)
    df["time"] = pd.to_datetime(df["time"].astype(float), unit="ms")

    path = _cache_path(symbol, interval)
    df.to_csv(path, index=False)
    print(f"[OK] Cached {len(df)} candles for {symbol} ({interval}) -> {path}")
    return df


def load_cached(symbol="BTCUSDT", interval="60"):
    """Load cached data from disk. Returns DataFrame or None."""
    path = _cache_path(symbol, interval)
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path)
    df["time"] = pd.to_datetime(df["time"])
    return df


def cache_age_minutes(symbol="BTCUSDT", interval="60"):
    """How many minutes old is the cache?"""
    path = _cache_path(symbol, interval)
    if not os.path.exists(path):
        return float("inf")
    return (time.time() - os.path.getmtime(path)) / 60


def refresh_all(interval="60", limit=1000):
    """Download fresh data for all symbols."""
    print("[*] Refreshing data cache for all symbols...")
    for sym in SYMBOLS:
        download_and_cache(sym, interval, limit)
    print("[OK] All caches refreshed!\n")


def get_data_smart(symbol="BTCUSDT", interval="60", limit=1000, max_age_minutes=60):
    """
    Smart loader: uses cache if fresh enough, otherwise downloads.
    This is the main entry point for the optimizer.
    """
    age = cache_age_minutes(symbol, interval)
    if age < max_age_minutes:
        df = load_cached(symbol, interval)
        if df is not None and len(df) > 0:
            return df

    return download_and_cache(symbol, interval, limit)


if __name__ == "__main__":
    refresh_all()
