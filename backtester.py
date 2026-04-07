"""
backtester.py — Professional Backtesting Engine
Strategy: EMA Crossover + RSI Filter + Volume Confirmation + ATR Dynamic Stops
Based on institutional-grade confluence trading (multi-indicator confirmation).
"""

import pandas as pd
import numpy as np
import json
import os
import requests

# ── Data fetching ────────────────────────────────────────────

def fetch_historical_data(symbol="BTCUSDT", interval="60", limit=1000):
    """Fetch kline data from Bybit Mainnet (free, no API key needed).
    interval 60 gives 1-hour candles. limit=1000 is maximum."""
    url = f"https://api.bybit.com/v5/market/kline?category=linear&symbol={symbol}&interval={interval}&limit={limit}"
    res = requests.get(url).json()
    
    if res.get("retCode") != 0:
        print(f"⚠️ Bybit API Error: {res.get('retMsg')}")
        return pd.DataFrame()
        
    klines = res["result"]["list"]
    klines.reverse()  # Bybit returns newest first, we need oldest first

    df = pd.DataFrame(klines, columns=[
        "time", "open", "high", "low", "close", "volume", "turnover"
    ])
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)
    df["time"] = pd.to_datetime(df["time"].astype(float), unit="ms")
    return df


# ── Indicator calculations ───────────────────────────────────

def add_indicators(df, ema_fast=9, ema_slow=21, rsi_period=14, atr_period=14, vol_ma_period=20):
    """Calculate all indicators used by the strategy."""
    # EMAs
    df["ema_fast"] = df["close"].ewm(span=ema_fast, adjust=False).mean()
    df["ema_slow"] = df["close"].ewm(span=ema_slow, adjust=False).mean()
    # 200 EMA trend filter
    df["ema_200"] = df["close"].ewm(span=200, adjust=False).mean()

    # RSI
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = (-delta.clip(upper=0))
    avg_gain = gain.ewm(span=rsi_period, adjust=False).mean()
    avg_loss = loss.ewm(span=rsi_period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["rsi"] = 100 - (100 / (1 + rs))

    # ATR (for dynamic stop loss)
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close = (df["low"] - df["close"].shift()).abs()
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df["atr"] = true_range.ewm(span=atr_period, adjust=False).mean()

    # Volume moving average (for volume confirmation)
    df["vol_ma"] = df["volume"].rolling(window=vol_ma_period).mean()

    return df


# ── Core backtester ──────────────────────────────────────────

def run_backtest(
    df,
    ema_fast=9,
    ema_slow=21,
    rsi_period=14,
    atr_period=14,
    rsi_buy_max=65,
    rsi_sell_min=35,
    atr_sl_mult=1.5,
    atr_tp_mult=3.0,
    qty=0.001,
    fee_bps=5,
    slippage_bps=3,
    require_volume=True,
    require_trend=True,
):
    """
    Run a full backtest with confluence-based entries and ATR-based exits.

    Entry rules (BUY):
      1. EMA fast crosses above EMA slow
      2. RSI < rsi_buy_max (not overbought)
      3. Volume > volume MA (confirmation, optional)
      4. Price > 200 EMA (trend filter, optional)

    Exit rules:
      - Stop loss  = entry - ATR * atr_sl_mult
      - Take profit = entry + ATR * atr_tp_mult
      - Or reverse signal (EMA fast crosses below EMA slow)

    Returns a dict of performance metrics.
    PnL is net of slippage and fees.
    """
    df = add_indicators(df.copy(), ema_fast, ema_slow, rsi_period, atr_period)
    df = df.dropna().reset_index(drop=True)

    trades = []
    in_position = False
    entry_price = 0
    stop_loss = 0
    take_profit = 0

    for i in range(1, len(df)):
        price = df["close"].iloc[i]
        atr = df["atr"].iloc[i]

        if not in_position:
            # ── BUY signal: confluence check ──
            ema_cross = (
                df["ema_fast"].iloc[i] > df["ema_slow"].iloc[i]
                and df["ema_fast"].iloc[i - 1] <= df["ema_slow"].iloc[i - 1]
            )
            rsi_ok = df["rsi"].iloc[i] < rsi_buy_max
            vol_ok = (not require_volume) or (df["volume"].iloc[i] > df["vol_ma"].iloc[i])
            trend_ok = (not require_trend) or (price > df["ema_200"].iloc[i])

            if ema_cross and rsi_ok and vol_ok and trend_ok:
                in_position = True
                entry_price = price
                stop_loss = price - atr * atr_sl_mult
                take_profit = price + atr * atr_tp_mult

        else:
            # ── Check exits ──
            hit_sl = price <= stop_loss
            hit_tp = price >= take_profit
            reverse_signal = (
                df["ema_fast"].iloc[i] < df["ema_slow"].iloc[i]
                and df["ema_fast"].iloc[i - 1] >= df["ema_slow"].iloc[i - 1]
            )

            if hit_sl or hit_tp or reverse_signal:
                exit_price = price
                # Model market-order costs on both legs.
                # BUY pays up (worse fill), SELL pays down.
                entry_fill = entry_price * (1 + slippage_bps / 10000)
                exit_fill = exit_price * (1 - slippage_bps / 10000)
                gross_pnl = (exit_fill - entry_fill) * qty
                fee_cost = (entry_fill * qty + exit_fill * qty) * (fee_bps / 10000)
                pnl = gross_pnl - fee_cost
                trades.append({
                    "entry": entry_price,
                    "exit": exit_price,
                    "entry_fill": round(entry_fill, 4),
                    "exit_fill": round(exit_fill, 4),
                    "qty": qty,
                    "gross_pnl": round(gross_pnl, 2),
                    "fee_cost": round(fee_cost, 2),
                    "pnl": round(pnl, 2),
                    "type": "TP" if hit_tp else ("SL" if hit_sl else "SIGNAL"),
                })
                in_position = False

    return _calc_metrics(trades)


# ── Metrics calculator ───────────────────────────────────────

def _calc_metrics(trades):
    """Calculate comprehensive performance metrics from a list of trades."""
    if not trades:
        return {
            "total_profit": 0, "win_rate": 0, "profit_factor": 0,
            "max_drawdown": 0, "sharpe": 0, "num_trades": 0,
            "equity_curve": [], "trades": [],
        }

    pnls = [t["pnl"] for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]

    total_profit = round(sum(pnls), 2)
    win_rate = round(len(wins) / len(pnls) * 100, 2) if pnls else 0
    profit_factor = (
        round(abs(sum(wins) / sum(losses)), 2) if losses else float("inf")
    )

    # Equity curve + max drawdown
    equity = []
    running = 0
    peak = 0
    max_dd = 0
    for p in pnls:
        running += p
        equity.append(round(running, 2))
        if running > peak:
            peak = running
        dd = (peak - running) / peak * 100 if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd
    max_dd = round(max_dd, 2)

    # Sharpe ratio (annualised, assuming ~365 trades/year for hourly)
    if len(pnls) > 1:
        mean_r = np.mean(pnls)
        std_r = np.std(pnls, ddof=1)
        sharpe = round((mean_r / std_r) * np.sqrt(365) if std_r != 0 else 0, 2)
    else:
        sharpe = 0

    return {
        "total_profit": total_profit,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "max_drawdown": max_dd,
        "sharpe": sharpe,
        "num_trades": len(pnls),
        "equity_curve": equity,
        "trades": trades,
    }


# ── Standalone test ──────────────────────────────────────────

if __name__ == "__main__":
    print("Fetching 1000 candles of BTCUSDT 1h data from Binance...")
    df = fetch_historical_data(limit=1000)
    print(f"Got {len(df)} candles. Running backtest with default EMA 9/21...")
    result = run_backtest(df)

    print("\n=== BACKTEST RESULTS ===")
    print(f"  Total Profit : ${result['total_profit']}")
    print(f"  Win Rate     : {result['win_rate']}%")
    print(f"  Profit Factor: {result['profit_factor']}")
    print(f"  Max Drawdown : {result['max_drawdown']}%")
    print(f"  Sharpe Ratio : {result['sharpe']}")
    print(f"  Total Trades : {result['num_trades']}")
