"""
performance.py — Advanced Performance Analytics Engine
Calculates: profit, win rate, profit factor, max drawdown, Sharpe ratio,
monthly returns, equity curve — all from trades.csv.
"""

import pandas as pd
import numpy as np
import os


TRADES_FILE = "trades.csv"


def _to_bool(val):
    if isinstance(val, bool):
        return val
    s = str(val).strip().lower()
    return s in {"1", "true", "yes", "y"}


def calculate_performance(symbol_filter="ALL"):
    """
    Parse trades.csv, pair BUY→SELL per symbol, and return metrics.
    Supports both legacy (5-column) and extended trade rows.
    """
    if not os.path.exists(TRADES_FILE) or os.path.getsize(TRADES_FILE) == 0:
        return _empty_metrics()

    try:
        df = pd.read_csv(TRADES_FILE, header=None, on_bad_lines="skip")
        expected_cols = [
            "time", "symbol", "signal", "price", "version",
            "qty", "order_id", "is_mock", "fee_bps", "slippage_bps",
        ]
        if df.shape[1] > len(expected_cols):
            df = df.iloc[:, :len(expected_cols)]
        df.columns = expected_cols[: df.shape[1]]
        for col in expected_cols:
            if col not in df.columns:
                df[col] = np.nan

        df["price"] = pd.to_numeric(df["price"], errors="coerce")
        df["time"] = pd.to_datetime(df["time"], errors="coerce")
        df["qty"] = pd.to_numeric(df["qty"], errors="coerce").fillna(0.001)
        df["fee_bps"] = pd.to_numeric(df["fee_bps"], errors="coerce").fillna(5.0)
        df["slippage_bps"] = pd.to_numeric(df["slippage_bps"], errors="coerce").fillna(3.0)
        df["order_id"] = df["order_id"].astype(str).fillna("")
        df["is_mock"] = df["is_mock"].apply(_to_bool)
        df["is_mock"] = df["is_mock"] | df["order_id"].str.startswith("mock_", na=False)
        df = df.dropna(subset=["price"])

        if symbol_filter != "ALL":
            df = df[df["symbol"] == symbol_filter]
    except Exception:
        return _empty_metrics()

    # ── Pair BUY → SELL per Symbol ──
    trades = []
    # Using a dict to track open positions per symbol
    open_buys = {}  # symbol -> buy row details

    for _, row in df.iterrows():
        sym = str(row["symbol"]).strip()
        sig = str(row["signal"]).strip().upper()

        if sig == "BUY":
            open_buys[sym] = {
                "price": float(row["price"]),
                "time": row["time"],
                "qty": float(row["qty"]),
                "fee_bps": float(row["fee_bps"]),
                "slippage_bps": float(row["slippage_bps"]),
                "is_mock": bool(row["is_mock"]),
            }
        elif sig == "SELL" and sym in open_buys:
            buy = open_buys[sym]
            sell_price = float(row["price"])
            qty = min(float(row["qty"]), buy["qty"]) if row["qty"] > 0 else buy["qty"]
            qty = max(qty, 0.0)

            buy_slip = buy["slippage_bps"] / 10000
            sell_slip = float(row["slippage_bps"]) / 10000
            buy_fee = buy["fee_bps"] / 10000
            sell_fee = float(row["fee_bps"]) / 10000

            entry_fill = buy["price"] * (1 + buy_slip)
            exit_fill = sell_price * (1 - sell_slip)
            gross_pnl = (exit_fill - entry_fill) * qty
            fee_cost = (entry_fill * qty * buy_fee) + (exit_fill * qty * sell_fee)
            pnl = gross_pnl - fee_cost
            is_mock_pair = bool(buy["is_mock"] or row["is_mock"])

            trades.append({
                "symbol": sym,
                "entry_time": buy["time"],
                "exit_time": row["time"],
                "entry_price": buy["price"],
                "exit_price": sell_price,
                "qty": round(qty, 6),
                "entry_fill": round(entry_fill, 4),
                "exit_fill": round(exit_fill, 4),
                "gross_pnl": round(gross_pnl, 2),
                "fee_cost": round(fee_cost, 2),
                "is_mock": is_mock_pair,
                "pnl": round(pnl, 2),
            })
            del open_buys[sym]

    real_trades = [t for t in trades if not t["is_mock"]]
    if not real_trades:
        return _empty_metrics()

    pnls = [t["pnl"] for t in real_trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]

    # ── Core metrics ──
    total_profit = round(sum(pnls), 2)
    win_rate = round(len(wins) / len(pnls) * 100, 2)
    profit_factor = (
        round(abs(sum(wins) / sum(losses)), 2) if losses else float("inf")
    )

    # ── Equity curve + Max drawdown ──
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

    # ── Sharpe ratio ──
    if len(pnls) > 1:
        mean_r = np.mean(pnls)
        std_r = np.std(pnls, ddof=1)
        sharpe = round((mean_r / std_r) * np.sqrt(252) if std_r != 0 else 0, 2)
    else:
        sharpe = 0

    # ── Monthly returns ──
    monthly = {}
    for t in real_trades:
        if pd.notna(t["exit_time"]):
            key = t["exit_time"].strftime("%Y-%m")
            monthly[key] = monthly.get(key, 0) + t["pnl"]
    monthly = {k: round(v, 2) for k, v in sorted(monthly.items())}

    # ── Consecutive losses (for self-learning detection) ──
    max_consec_loss = 0
    current_streak = 0
    for p in pnls:
        if p < 0:
            current_streak += 1
            max_consec_loss = max(max_consec_loss, current_streak)
        else:
            current_streak = 0

    return {
        "total_profit": total_profit,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "max_drawdown": max_dd,
        "sharpe": sharpe,
        "num_trades": len(pnls),
        "equity_curve": equity,
        "monthly_returns": monthly,
        "max_consecutive_losses": max_consec_loss,
        "trades": real_trades,
        "total_signals": len(df),
        "real_trades": len(real_trades),
        "mock_trades": len(trades) - len(real_trades),
    }


def _empty_metrics():
    return {
        "total_profit": 0,
        "win_rate": 0,
        "profit_factor": 0,
        "max_drawdown": 0,
        "sharpe": 0,
        "num_trades": 0,
        "equity_curve": [],
        "monthly_returns": {},
        "max_consecutive_losses": 0,
        "trades": [],
        "total_signals": 0,
        "real_trades": 0,
        "mock_trades": 0,
    }