"""
strategy_engine.py — Live Strategy Engine
Loads optimized parameters from config.json.
Runs EMA + RSI + Volume + ATR strategy.
Runtime behavior is controlled by config runtime keys.
"""

import datetime
import json
import os
import sys
import tempfile
import time

import numpy as np
import pandas as pd
import requests

import executor

CONFIG_FILE = "config.json"
TRADES_FILE = "trades.csv"
STATUS_FILE = "runtime_status.json"
RE_OPTIMIZE_EVERY = 20
MIN_ORDER_QTY = 0.001

DEFAULT_RUNTIME = {
    "risk_profile": "Balanced",
    "exchange_mode": "demo",
    "fail_safe_mode": "A_hard_stop",  # A_hard_stop | B_internal_paper_fallback | C_retry_then_stop
    "risk_per_trade_pct": 0.005,
    "fee_bps": 5.0,
    "slippage_bps": 3.0,
    "max_daily_loss_usd": 50.0,
    "cooldown_minutes": 30,
    "max_consecutive_losses": 4,
    "max_open_positions": 2,
    "max_mock_orders_streak": 3,
    "retry_attempts": 5,
    "retry_interval_sec": 15,
    "cooldown_after_stop_min": 30,
}


def load_params():
    defaults = {
        "ema_fast": 9,
        "ema_slow": 21,
        "rsi_buy_max": 65,
        "atr_sl_mult": 1.5,
        "atr_tp_mult": 3.0,
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                cfg = json.load(f)
            return cfg.get("best_params", defaults)
        except Exception:
            pass
    return defaults


def load_runtime_settings():
    runtime = DEFAULT_RUNTIME.copy()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                cfg = json.load(f)
            runtime.update(cfg.get("runtime", {}))
        except Exception:
            pass
    return runtime


def _atomic_write_json(path, payload):
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix="runtime_status_", suffix=".json", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        os.replace(temp_path, path)
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass


def write_runtime_status(payload):
    payload["updated_at"] = datetime.datetime.now().isoformat()
    _atomic_write_json(STATUS_FILE, payload)


def get_data(symbol="BTCUSDT", interval="5", limit=500):
    """Use public market data for signals; execution route is controlled in executor."""
    url = f"https://api.bybit.com/v5/market/kline?category=linear&symbol={symbol}&interval={interval}&limit={limit}"
    try:
        res = requests.get(url, timeout=10).json()
    except Exception as e:
        print(f"[!] Network error fetching {symbol}: {e}", flush=True)
        return pd.DataFrame()

    if res.get("retCode") != 0:
        print(f"[!] API Error fetching {symbol}: {res.get('retMsg')}", flush=True)
        return pd.DataFrame()

    klines = res["result"]["list"]
    if not klines:
        print(f"[!] No klines returned for {symbol}", flush=True)
        return pd.DataFrame()
    klines.reverse()

    df = pd.DataFrame(klines, columns=["time", "open", "high", "low", "close", "volume", "turnover"])
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)
    return df


def calc_indicators(df, params):
    ef = params["ema_fast"]
    es = params["ema_slow"]
    df["ema_fast"] = df["close"].ewm(span=ef, adjust=False).mean()
    df["ema_slow"] = df["close"].ewm(span=es, adjust=False).mean()
    df["ema_200"] = df["close"].ewm(span=200, adjust=False).mean()

    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = (-delta.clip(upper=0))
    avg_gain = gain.ewm(span=14, adjust=False).mean()
    avg_loss = loss.ewm(span=14, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["rsi"] = 100 - (100 / (1 + rs))

    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close = (df["low"] - df["close"].shift()).abs()
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df["atr"] = true_range.ewm(span=14, adjust=False).mean()
    df["vol_ma"] = df["volume"].rolling(window=20).mean()
    return df


def check_signal(df, params):
    if len(df) < 2:
        return "HOLD", 0, 0

    i = len(df) - 1
    prev = i - 1
    price = df["close"].iloc[i]
    atr = df["atr"].iloc[i]
    rsi = df["rsi"].iloc[i]
    ema_f = df["ema_fast"].iloc[i]
    ema_s = df["ema_slow"].iloc[i]
    ema_f_prev = df["ema_fast"].iloc[prev]
    ema_s_prev = df["ema_slow"].iloc[prev]
    ema200 = df["ema_200"].iloc[i]

    buy_cross = ema_f > ema_s and ema_f_prev <= ema_s_prev
    buy_rsi = rsi < params.get("rsi_buy_max", 65)
    buy_vol = df["volume"].iloc[i] > df["vol_ma"].iloc[i]
    buy_trend = price > ema200
    if buy_cross and buy_rsi and buy_vol and buy_trend:
        return "BUY", price, atr

    sell_cross = ema_f < ema_s and ema_f_prev >= ema_s_prev
    if sell_cross:
        return "SELL", price, atr
    return "HOLD", price, atr


def log_trade(symbol, signal, price, params, qty, order_id, is_mock, fee_bps, slippage_bps):
    version = f"EMA{params['ema_fast']}_{params['ema_slow']}"
    with open(TRADES_FILE, "a") as f:
        f.write(
            f"{datetime.datetime.now()},{symbol},{signal},{price},{version},"
            f"{qty},{order_id},{is_mock},{fee_bps},{slippage_bps}\n"
        )


def estimate_net_pnl(entry_price, exit_price, qty, fee_bps, slippage_bps):
    entry_fill = entry_price * (1 + slippage_bps / 10000)
    exit_fill = exit_price * (1 - slippage_bps / 10000)
    gross = (exit_fill - entry_fill) * qty
    fees = (entry_fill * qty + exit_fill * qty) * (fee_bps / 10000)
    return gross - fees


def calc_order_qty(entry_price, atr, atr_sl_mult, risk_per_trade_pct):
    stop_distance = max(atr * atr_sl_mult, 1e-9)
    try:
        bal = executor.get_usdt_balance()
    except Exception:
        bal = 10000.0
    risk_usd = max(bal * risk_per_trade_pct, 1.0)
    qty = risk_usd / stop_distance
    max_qty = max((bal * 0.1) / max(entry_price, 1e-9), MIN_ORDER_QTY)
    qty = min(max(qty, MIN_ORDER_QTY), max_qty)
    return round(qty, 6)


def count_recent_trades():
    if not os.path.exists(TRADES_FILE):
        return 0
    try:
        df = pd.read_csv(TRADES_FILE, header=None, on_bad_lines="skip")
        return len(df)
    except Exception:
        return 0


def trigger_reoptimize():
    print("\n[*] AUTO RE-OPTIMIZATION TRIGGERED", flush=True)
    print("=" * 50, flush=True)
    try:
        from optimizer import optimize
        optimize()
        print("[OK] Re-optimization complete. New params loaded.\n", flush=True)
    except Exception as e:
        print(f"[X] Re-optimization failed: {e}\n", flush=True)


def check_performance_threshold():
    try:
        from performance import calculate_performance
        metrics = calculate_performance()
        pf = metrics.get("profit_factor", 0)
        wr = metrics.get("win_rate", 0)
        dd = metrics.get("max_drawdown", 0)
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                cfg = json.load(f)
            filters = cfg.get("filters", {})
        else:
            filters = {"min_profit_factor": 1.5, "min_win_rate": 50, "max_drawdown": 25}
        return (
            (pf < filters.get("min_profit_factor", 1.5) and pf > 0)
            or (wr < filters.get("min_win_rate", 50) and wr > 0)
            or dd > filters.get("max_drawdown", 25)
        )
    except Exception:
        return False


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)

    params = load_params()
    runtime = load_runtime_settings()
    fee_bps = float(runtime.get("fee_bps", DEFAULT_RUNTIME["fee_bps"]))
    slippage_bps = float(runtime.get("slippage_bps", DEFAULT_RUNTIME["slippage_bps"]))
    max_daily_loss_usd = float(runtime.get("max_daily_loss_usd", DEFAULT_RUNTIME["max_daily_loss_usd"]))
    cooldown_minutes = int(runtime.get("cooldown_minutes", DEFAULT_RUNTIME["cooldown_minutes"]))
    risk_per_trade_pct = float(runtime.get("risk_per_trade_pct", DEFAULT_RUNTIME["risk_per_trade_pct"]))
    max_consecutive_losses = int(runtime.get("max_consecutive_losses", DEFAULT_RUNTIME["max_consecutive_losses"]))
    max_open_positions = int(runtime.get("max_open_positions", DEFAULT_RUNTIME["max_open_positions"]))
    max_mock_orders_streak = int(runtime.get("max_mock_orders_streak", DEFAULT_RUNTIME["max_mock_orders_streak"]))
    exchange_mode = str(runtime.get("exchange_mode", DEFAULT_RUNTIME["exchange_mode"]))
    fail_safe_mode = str(runtime.get("fail_safe_mode", DEFAULT_RUNTIME["fail_safe_mode"]))
    retry_attempts = int(runtime.get("retry_attempts", DEFAULT_RUNTIME["retry_attempts"]))
    retry_interval_sec = int(runtime.get("retry_interval_sec", DEFAULT_RUNTIME["retry_interval_sec"]))
    cooldown_after_stop_min = int(runtime.get("cooldown_after_stop_min", DEFAULT_RUNTIME["cooldown_after_stop_min"]))
    connectivity_failures = 0

    print("=== STRATEGY ENGINE STARTED ===", flush=True)
    print(f"  EMA Fast    : {params['ema_fast']}", flush=True)
    print(f"  EMA Slow    : {params['ema_slow']}", flush=True)
    print(f"  RSI Buy Max : {params['rsi_buy_max']}", flush=True)
    print(f"  ATR SL Mult : {params['atr_sl_mult']}", flush=True)
    print(f"  ATR TP Mult : {params['atr_tp_mult']}", flush=True)
    print(f"  Risk Profile: {runtime.get('risk_profile', 'Balanced')}", flush=True)
    print(f"  Exchange    : {exchange_mode}", flush=True)
    print(f"  Fail-safe   : {fail_safe_mode}", flush=True)
    print(f"  Risk/Trade  : {risk_per_trade_pct*100:.2f}%", flush=True)
    print(f"  Fee/Slip bps: {fee_bps}/{slippage_bps}", flush=True)
    print(f"  Re-optimize every {RE_OPTIMIZE_EVERY} trades", flush=True)
    print("-" * 40, flush=True)

    symbols = ["BTCUSDT", "XAUUSDT", "XAGUSDT"]
    positions = {s: {"active": False, "entry": 0, "sl": 0, "tp": 0} for s in symbols}
    day_key = datetime.datetime.now().date().isoformat()
    daily_net_pnl = 0.0
    cooldown_until = None
    consecutive_losses = 0
    mock_order_streak = 0
    kill_switch = False
    last_trade_count = count_recent_trades()

    while True:
        try:
            health = executor.check_connection()
            conn_ok = bool(health.get("can_trade", False))
            if conn_ok:
                connectivity_failures = 0
            else:
                connectivity_failures += 1

            fallback_to_internal_sim = False
            if not conn_ok:
                if fail_safe_mode == "A_hard_stop":
                    kill_switch = True
                elif fail_safe_mode == "B_internal_paper_fallback":
                    fallback_to_internal_sim = True
                elif fail_safe_mode == "C_retry_then_stop":
                    if connectivity_failures >= retry_attempts:
                        kill_switch = True
                        cooldown_until = datetime.datetime.now() + datetime.timedelta(minutes=cooldown_after_stop_min)
                    else:
                        print(
                            f"[SAFE] Connectivity retry {connectivity_failures}/{retry_attempts}. "
                            f"Waiting {retry_interval_sec}s before next loop.",
                            flush=True,
                        )
                        time.sleep(max(retry_interval_sec, 1))
                        continue

            status_payload = {
                "engine_state": "running",
                "exchange_mode": exchange_mode,
                "fail_safe_mode": fail_safe_mode,
                "connectivity_failures": connectivity_failures,
                "connectivity_health": health,
                "kill_switch": kill_switch,
                "cooldown_until": cooldown_until.isoformat() if cooldown_until else None,
                "daily_net_pnl": round(daily_net_pnl, 2),
                "consecutive_losses": consecutive_losses,
                "mock_order_streak": mock_order_streak,
                "positions": positions,
                "last_signal": {},
                "last_order": {},
                "events": [],
            }

            for symbol in symbols:
                now = datetime.datetime.now()
                current_day = now.date().isoformat()
                if current_day != day_key:
                    day_key = current_day
                    daily_net_pnl = 0.0
                    cooldown_until = None
                    consecutive_losses = 0

                df = get_data(symbol)
                if df.empty or len(df) < 50:
                    print(f"[!] Insufficient data for {symbol}, skipping...", flush=True)
                    continue
                df = calc_indicators(df, params).dropna()
                if df.empty:
                    continue

                signal, price, atr = check_signal(df, params)
                status_payload["last_signal"][symbol] = {
                    "signal": signal,
                    "price": round(float(price), 4) if price else 0,
                    "atr": round(float(atr), 4) if atr else 0,
                    "position_active": bool(positions[symbol]["active"]),
                }

                if not positions[symbol]["active"] and signal == "BUY":
                    if kill_switch:
                        print("[RISK] Kill-switch active. Skipping entries.", flush=True)
                        status_payload["events"].append({"symbol": symbol, "type": "blocked", "reason": "kill_switch"})
                        continue

                    active_count = sum(1 for p in positions.values() if p["active"])
                    if active_count >= max_open_positions:
                        print(f"[RISK] Max open positions reached ({max_open_positions}).", flush=True)
                        status_payload["events"].append({"symbol": symbol, "type": "blocked", "reason": "max_open_positions"})
                        continue

                    if cooldown_until and now < cooldown_until:
                        mins_left = int((cooldown_until - now).total_seconds() // 60) + 1
                        print(f"[RISK] Cooldown active ({mins_left}m left).", flush=True)
                        status_payload["events"].append({"symbol": symbol, "type": "blocked", "reason": "cooldown"})
                        continue

                    qty = calc_order_qty(price, atr, params["atr_sl_mult"], risk_per_trade_pct)
                    positions[symbol]["active"] = True
                    positions[symbol]["entry"] = price
                    positions[symbol]["sl"] = price - atr * params["atr_sl_mult"]
                    positions[symbol]["tp"] = price + atr * params["atr_tp_mult"]
                    positions[symbol]["qty"] = qty

                    order_id = (
                        f"paper_fallback_{int(time.time()*1000)}"
                        if fallback_to_internal_sim
                        else executor.place_market_order(symbol=symbol, side="BUY", qty=qty)
                    )
                    is_mock = str(order_id).startswith("mock_")
                    is_fallback = str(order_id).startswith("paper_fallback_")
                    mock_order_streak = mock_order_streak + 1 if is_mock else 0
                    if mock_order_streak >= max_mock_orders_streak:
                        kill_switch = True
                        print("[RISK] Kill-switch engaged: too many consecutive mock orders.", flush=True)

                    log_trade(symbol, "BUY", price, params, qty, order_id, (is_mock or is_fallback), fee_bps, slippage_bps)
                    status_payload["last_order"] = {
                        "symbol": symbol,
                        "side": "BUY",
                        "qty": qty,
                        "order_id": order_id,
                        "is_mock": bool(is_mock),
                        "is_fallback": bool(is_fallback),
                    }
                    status_payload["events"].append({"symbol": symbol, "type": "order", "side": "BUY", "order_id": order_id})
                    print(
                        f"[BUY] @ ${price:.2f} ({symbol}) | Qty: {qty} | "
                        f"SL: ${positions[symbol]['sl']:.2f} | TP: ${positions[symbol]['tp']:.2f} | OrderID: {order_id}",
                        flush=True,
                    )

                elif positions[symbol]["active"]:
                    hit_sl = price <= positions[symbol]["sl"]
                    hit_tp = price >= positions[symbol]["tp"]
                    reverse = signal == "SELL"
                    if hit_sl or hit_tp or reverse:
                        exit_type = "TP" if hit_tp else ("SL" if hit_sl else "SIGNAL")
                        qty = positions[symbol].get("qty", MIN_ORDER_QTY)
                        pnl = estimate_net_pnl(positions[symbol]["entry"], price, qty, fee_bps, slippage_bps)

                        order_id = (
                            f"paper_fallback_{int(time.time()*1000)}"
                            if fallback_to_internal_sim
                            else executor.place_market_order(symbol=symbol, side="SELL", qty=qty)
                        )
                        is_mock = str(order_id).startswith("mock_")
                        is_fallback = str(order_id).startswith("paper_fallback_")
                        mock_order_streak = mock_order_streak + 1 if is_mock else 0
                        if mock_order_streak >= max_mock_orders_streak:
                            kill_switch = True
                            print("[RISK] Kill-switch engaged: too many consecutive mock orders.", flush=True)

                        log_trade(symbol, "SELL", price, params, qty, order_id, (is_mock or is_fallback), fee_bps, slippage_bps)
                        status_payload["last_order"] = {
                            "symbol": symbol,
                            "side": "SELL",
                            "qty": qty,
                            "order_id": order_id,
                            "is_mock": bool(is_mock),
                            "is_fallback": bool(is_fallback),
                            "pnl": round(float(pnl), 2),
                            "exit_type": exit_type,
                        }
                        status_payload["events"].append(
                            {"symbol": symbol, "type": "order", "side": "SELL", "order_id": order_id, "pnl": round(float(pnl), 2)}
                        )
                        print(
                            f"[SELL] @ ${price:.2f} ({symbol}) | Qty: {qty} | "
                            f"PnL: ${pnl:+.2f} | Exit: {exit_type} | OrderID: {order_id}",
                            flush=True,
                        )
                        if not is_mock:
                            daily_net_pnl += pnl
                            consecutive_losses = consecutive_losses + 1 if pnl < 0 else 0
                            if consecutive_losses >= max_consecutive_losses:
                                cooldown_until = now + datetime.timedelta(minutes=cooldown_minutes)
                            if daily_net_pnl <= -abs(max_daily_loss_usd):
                                cooldown_until = now + datetime.timedelta(minutes=cooldown_minutes)
                        positions[symbol] = {"active": False, "entry": 0, "sl": 0, "tp": 0}
                else:
                    rsi_val = df["rsi"].iloc[-1]
                    print(f"[HOLD] Price: ${price:.2f} ({symbol}) | RSI: {rsi_val:.1f}", flush=True)

            current_count = count_recent_trades()
            if current_count - last_trade_count >= RE_OPTIMIZE_EVERY:
                print(f"\n[*] {RE_OPTIMIZE_EVERY} trades completed. Checking performance...", flush=True)
                if check_performance_threshold():
                    trigger_reoptimize()
                    params = load_params()
                    print(f"[*] Now using: EMA {params['ema_fast']}/{params['ema_slow']}", flush=True)
                else:
                    print("[OK] Performance within thresholds. No changes needed.\n", flush=True)
                last_trade_count = current_count

            write_runtime_status(status_payload)
        except Exception as e:
            print(f"[!] Error: {e}", flush=True)
            write_runtime_status(
                {
                    "engine_state": "error",
                    "error": str(e),
                    "exchange_mode": exchange_mode,
                    "fail_safe_mode": fail_safe_mode,
                    "kill_switch": kill_switch,
                    "cooldown_until": cooldown_until.isoformat() if cooldown_until else None,
                }
            )
        time.sleep(60)


if __name__ == "__main__":
    main()