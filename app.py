"""
AMATS Trading Dashboard — Flask Backend
-----------------------------------------
Serves the 3D frontend and provides API endpoints for:
- Live market prices (Bybit mainnet public API)
- Engine status (from runtime_status.json)
- Real trades (from trades.csv)
- Backtest performance (from performance.py)
"""

import json
import os
import threading
import time
from datetime import datetime

import pandas as pd
import requests
from flask import Flask, jsonify, send_from_directory

from performance import calculate_performance

app = Flask(__name__, static_folder="static", static_url_path="/static")

CONFIG_FILE = "config.json"
RUNTIME_STATUS_FILE = "runtime_status.json"
TRADES_FILE = "trades.csv"
WATCHLIST = ["BTCUSDT", "XAUUSDT", "XAGUSDT"]
YAHOO_MAP = {"BTCUSDT": "BTC-USD", "XAUUSDT": "GC=F", "XAGUSDT": "SI=F"}
NAME_MAP = {
    "BTCUSDT": {"name": "BTC / USDT", "full": "Bitcoin Perpetual"},
    "XAUUSDT": {"name": "GOLD / PAXG", "full": "Gold Spot"},
    "XAGUSDT": {"name": "SILVER / AGLD", "full": "Silver Spot"},
}


# ─── Helpers ───

def load_json(path: str, default=None):
    if default is None:
        default = {}
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def load_trade_signals() -> pd.DataFrame:
    if not os.path.exists(TRADES_FILE) or os.path.getsize(TRADES_FILE) == 0:
        return pd.DataFrame()
    try:
        df = pd.read_csv(TRADES_FILE, header=None, on_bad_lines="skip")
    except Exception:
        return pd.DataFrame()

    expected_cols = [
        "time", "symbol", "signal", "price", "version",
        "qty", "order_id", "is_mock", "fee_bps", "slippage_bps",
    ]
    if df.shape[1] > len(expected_cols):
        df = df.iloc[:, :len(expected_cols)]
    df.columns = expected_cols[:df.shape[1]]

    for col in expected_cols:
        if col not in df.columns:
            df[col] = pd.NA

    df["time"] = pd.to_datetime(df["time"], errors="coerce")
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df["qty"] = pd.to_numeric(df["qty"], errors="coerce")
    return df.dropna(subset=["time"]).sort_values("time", ascending=False)


def safe_float(value, fallback=0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(fallback)


def fetch_market_snapshot_bybit(symbol: str) -> dict:
    """Fetch from Bybit public mainnet API (no auth needed)."""
    url = f"https://api.bybit.com/v5/market/tickers?category=linear&symbol={symbol}"
    try:
        res = requests.get(url, timeout=8)
        payload = res.json()
        if payload.get("retCode") != 0:
            return {"ok": False, "reason": payload.get("retMsg", "Bybit rejected")}
        item = payload.get("result", {}).get("list", [{}])[0]
        if not item.get("lastPrice"):
            return {"ok": False, "reason": "Empty ticker"}
        price = float(item.get("lastPrice"))
        change = float(item.get("price24hPcnt", 0.0)) * 100
        vol_24h = float(item.get("volume24h", 0))
        high_24h = float(item.get("highPrice24h", 0))
        low_24h = float(item.get("lowPrice24h", 0))
        return {
            "ok": True, "price": price, "change_24h": change,
            "vol_24h": vol_24h, "high_24h": high_24h, "low_24h": low_24h,
            "source": "Bybit",
        }
    except Exception as exc:
        return {"ok": False, "reason": f"Bybit: {exc}"}


def fetch_market_snapshot_yahoo(symbol: str) -> dict:
    ticker = YAHOO_MAP.get(symbol)
    if not ticker:
        return {"ok": False, "reason": "No Yahoo mapping"}
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=2d&interval=1d"
    try:
        res = requests.get(url, timeout=8)
        payload = res.json()
        result = payload.get("chart", {}).get("result", [])
        if not result:
            return {"ok": False, "reason": "Yahoo: no result"}
        meta = result[0].get("meta", {})
        price = meta.get("regularMarketPrice")
        prev_close = meta.get("chartPreviousClose")
        if price is None:
            return {"ok": False, "reason": "Yahoo: no price"}
        change = None
        if prev_close not in (None, 0):
            change = ((float(price) - float(prev_close)) / float(prev_close)) * 100
        return {"ok": True, "price": float(price), "change_24h": change, "source": "Yahoo"}
    except Exception as exc:
        return {"ok": False, "reason": f"Yahoo: {exc}"}


def fetch_market_snapshot(symbol: str) -> dict:
    default = {
        "symbol": symbol, "price": None, "change_24h": None,
        "source": "Unavailable", "status": "unavailable",
    }
    meta = NAME_MAP.get(symbol, {"name": symbol, "full": symbol})

    bybit = fetch_market_snapshot_bybit(symbol)
    if bybit.get("ok"):
        return {
            "symbol": symbol, "name": meta["name"], "full_name": meta["full"],
            "price": bybit["price"], "change_24h": bybit.get("change_24h"),
            "vol_24h": bybit.get("vol_24h"), "high_24h": bybit.get("high_24h"),
            "low_24h": bybit.get("low_24h"), "source": bybit["source"], "status": "live",
        }

    yahoo = fetch_market_snapshot_yahoo(symbol)
    if yahoo.get("ok"):
        return {
            "symbol": symbol, "name": meta["name"], "full_name": meta["full"],
            "price": yahoo["price"], "change_24h": yahoo.get("change_24h"),
            "source": yahoo["source"], "status": "fallback",
        }
    default.update({"name": meta["name"], "full_name": meta["full"]})
    return default


# ─── Routes ───

@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/prices")
def api_prices():
    prices = [fetch_market_snapshot(sym) for sym in WATCHLIST]
    return jsonify({"prices": prices, "timestamp": datetime.now().isoformat()})


@app.route("/api/engine-status")
def api_engine_status():
    """Return live engine state from runtime_status.json."""
    status = load_json(RUNTIME_STATUS_FILE, {})
    config = load_json(CONFIG_FILE, {})
    runtime = config.get("runtime", {})
    params = config.get("best_params", {})

    return jsonify({
        "engine_state": status.get("engine_state", "stopped"),
        "exchange_mode": status.get("exchange_mode", runtime.get("exchange_mode", "testnet")),
        "kill_switch": status.get("kill_switch", False),
        "daily_net_pnl": safe_float(status.get("daily_net_pnl", 0)),
        "consecutive_losses": status.get("consecutive_losses", 0),
        "mock_order_streak": status.get("mock_order_streak", 0),
        "cooldown_until": status.get("cooldown_until"),
        "connectivity": status.get("connectivity_health", {}),
        "positions": status.get("positions", {}),
        "last_signal": status.get("last_signal", {}),
        "last_order": status.get("last_order", {}),
        "events": status.get("events", []),
        "updated_at": status.get("updated_at"),
        "strategy_params": params,
        "risk_profile": runtime.get("risk_profile", "Balanced"),
        "risk_per_trade_pct": runtime.get("risk_per_trade_pct", 0.005),
        "max_daily_loss_usd": runtime.get("max_daily_loss_usd", 50),
        "max_open_positions": runtime.get("max_open_positions", 2),
    })


@app.route("/api/trades")
def api_trades():
    """Return real trade data from trades.csv."""
    df = load_trade_signals()
    if df.empty:
        return jsonify({"trades": [], "count": 0})

    trades = []
    for _, row in df.head(50).iterrows():
        trade = {
            "time": str(row.get("time", "")),
            "symbol": str(row.get("symbol", "")),
            "signal": str(row.get("signal", "")),
            "price": safe_float(row.get("price")),
            "version": str(row.get("version", "")),
            "qty": safe_float(row.get("qty")),
            "order_id": str(row.get("order_id", "")),
            "is_mock": bool(str(row.get("is_mock", "")).lower() in ("true", "1", "yes")),
        }
        trades.append(trade)

    return jsonify({"trades": trades, "count": len(df)})


@app.route("/api/performance")
def api_performance():
    """Return real performance metrics from trades.csv."""
    metrics = calculate_performance()
    return jsonify({
        "total_profit": safe_float(metrics.get("total_profit", 0)),
        "win_rate": safe_float(metrics.get("win_rate", 0)),
        "profit_factor": metrics.get("profit_factor", 0),
        "max_drawdown": safe_float(metrics.get("max_drawdown", 0)),
        "sharpe": metrics.get("sharpe", 0),
        "num_trades": metrics.get("num_trades", 0),
        "total_signals": metrics.get("total_signals", 0),
        "real_trades": metrics.get("real_trades", 0),
        "mock_trades": metrics.get("mock_trades", 0),
        "equity_curve": metrics.get("equity_curve", []),
        "monthly_returns": metrics.get("monthly_returns", {}),
        "max_consecutive_losses": metrics.get("max_consecutive_losses", 0),
    })


@app.route("/api/config")
def api_config():
    """Return strategy config for the dashboard."""
    config = load_json(CONFIG_FILE, {})
    return jsonify({
        "best_params": config.get("best_params", {}),
        "filters": config.get("filters", {}),
        "runtime": config.get("runtime", {}),
        "last_optimized": config.get("last_optimized"),
        "validation": config.get("validation", {}),
    })


# ─── Main ───

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n>>> AMATS Dashboard running at http://localhost:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=True)
