"""
optimizer.py — Grid-Search Optimization Engine
Tests hundreds of parameter combinations, ranks by composite score,
saves the best config, and maintains version history.
"""

import json
import os
import itertools
from datetime import datetime
import statistics
from backtester import run_backtest
from data_cache import get_data_smart

CONFIG_FILE = "config.json"
ASSETS = ["BTCUSDT", "XAUUSDT", "XAGUSDT"]

# ── Performance thresholds (mandatory filters) ───────────────

FILTERS = {
    "min_profit_factor": 1.10,
    "min_win_rate": 45,
    "max_drawdown": 30,
    "min_trades": 20,
}

# ── Parameter grid (practical and fast) ──────────────────────

PARAM_GRID = {
    "ema_fast": [5, 9, 12, 15, 20, 25],
    "ema_slow": [21, 30, 40, 50, 60, 80],
    "rsi_buy_max": [60, 65, 70],
    "atr_sl_mult": [1.0, 1.5, 2.0],
    "atr_tp_mult": [2.0, 3.0, 4.0],
}


def _composite_score(m):
    """Weighted score: PF 45%, WR 20%, low DD 20%, Sharpe 15%."""
    pf_score = min(m["profit_factor"], 5) / 5  # cap at 5
    wr_score = m["win_rate"] / 100
    dd_score = 1 - (m["max_drawdown"] / 100)
    sharpe_score = min(max(m.get("sharpe", 0), -1), 3) / 3
    return round(pf_score * 0.45 + wr_score * 0.20 + dd_score * 0.20 + sharpe_score * 0.15, 4)


def _passes_filter(m):
    """Check if a result meets all mandatory criteria."""
    return (
        m["profit_factor"] >= FILTERS["min_profit_factor"]
        and m["win_rate"] >= FILTERS["min_win_rate"]
        and m["max_drawdown"] <= FILTERS["max_drawdown"]
        and m["num_trades"] >= FILTERS["min_trades"]
    )


def _walk_forward_slices(df_len, train_size=420, test_size=180, step_size=120):
    """Build walk-forward windows over index ranges."""
    windows = []
    i = 0
    while i + train_size + test_size <= df_len:
        windows.append((i, i + train_size, i + train_size + test_size))
        i += step_size
    return windows


def _aggregate_metrics(metric_list):
    if not metric_list:
        return {}
    keys = ["total_profit", "win_rate", "profit_factor", "max_drawdown", "sharpe", "num_trades"]
    out = {}
    for k in keys:
        vals = [m.get(k, 0) for m in metric_list]
        out[k] = round(sum(vals) / len(vals), 2)
    return out


def _evaluate_on_walk_forward(df, params, windows):
    """Return average out-of-sample metrics across walk-forward test windows."""
    oos_results = []
    for _, train_end, test_end in windows:
        # Train section is not used directly for fitting here; optimizer chooses params globally.
        # Walk-forward purpose in this setup is repeated OOS validation across time windows.
        df_test = df.iloc[train_end:test_end].reset_index(drop=True)
        if len(df_test) < 100:
            continue
        m = run_backtest(
            df_test,
            ema_fast=params["ema_fast"],
            ema_slow=params["ema_slow"],
            rsi_buy_max=params["rsi_buy_max"],
            atr_sl_mult=params["atr_sl_mult"],
            atr_tp_mult=params["atr_tp_mult"],
        )
        oos_results.append(m)
    return _aggregate_metrics(oos_results), oos_results


def optimize(symbol="ALL", interval="60", limit=2400):
    """
    Run robust grid-search optimization.
    1. Fetch historical data (cached) for one or many assets
    2. Score combos on in-sample data with stricter filters
    3. Validate shortlisted combos with walk-forward out-of-sample windows
    4. Aggregate results across assets
    5. Save best to config.json
    """
    print("=== OPTIMIZER STARTING ===")
    print(f"Symbol scope: {symbol}  |  Interval: {interval}  |  Candles: {limit}")
    print(f"Filters: {FILTERS}\n")

    symbols = ASSETS if symbol == "ALL" else [symbol]
    datasets = {}
    for sym in symbols:
        print(f"Loading data for {sym}...")
        df = get_data_smart(sym, interval, limit)
        if df is None or df.empty or len(df) < 800:
            print(f"  [!] Skipping {sym}: insufficient candles ({0 if df is None else len(df)})")
            continue
        datasets[sym] = df.reset_index(drop=True)
        print(f"  [OK] {sym}: {len(df)} candles")
    print("")

    if not datasets:
        print("FAILED: No valid datasets found. Using defaults.")
        best = {"ema_fast": 9, "ema_slow": 21, "rsi_buy_max": 65, "atr_sl_mult": 1.5, "atr_tp_mult": 3.0}
        _save_config(best, {}, {}, {"reason": "no_data"})
        return best

    # ── Generate valid combos (fast < slow) ──
    keys = list(PARAM_GRID.keys())
    all_combos = list(itertools.product(*PARAM_GRID.values()))
    valid_combos = [
        dict(zip(keys, combo))
        for combo in all_combos
        if combo[0] < combo[1]  # ema_fast < ema_slow
    ]
    print(f"Testing {len(valid_combos)} parameter combinations across {len(datasets)} asset(s)...\n")

    # ── First pass: in-sample robustness across assets ──
    results = []
    for i, params in enumerate(valid_combos):
        if (i + 1) % 50 == 0 or i == 0:
            print(f"  Progress: {i + 1}/{len(valid_combos)}")

        asset_metrics = {}
        asset_scores = []
        passed_assets = 0

        for sym, df in datasets.items():
            split = int(len(df) * 0.7)
            df_train = df.iloc[:split].reset_index(drop=True)
            m = run_backtest(
                df_train,
                ema_fast=params["ema_fast"],
                ema_slow=params["ema_slow"],
                rsi_buy_max=params["rsi_buy_max"],
                atr_sl_mult=params["atr_sl_mult"],
                atr_tp_mult=params["atr_tp_mult"],
            )
            asset_metrics[sym] = m
            if _passes_filter(m):
                passed_assets += 1
            asset_scores.append(_composite_score(m))

        if passed_assets >= max(1, len(datasets) // 2):
            results.append({
                **params,
                "in_sample_score": round(sum(asset_scores) / len(asset_scores), 4),
                "asset_metrics": asset_metrics,
                "assets_passed": passed_assets,
            })

    if not results:
        print("\nWARNING: No combinations passed all filters.")
        print("    Relaxing constraints and retrying quick pass...")
        for params in valid_combos:
            asset_scores = []
            for sym, df in datasets.items():
                split = int(len(df) * 0.7)
                m = run_backtest(
                    df.iloc[:split].reset_index(drop=True),
                    ema_fast=params["ema_fast"],
                    ema_slow=params["ema_slow"],
                    rsi_buy_max=params["rsi_buy_max"],
                    atr_sl_mult=params["atr_sl_mult"],
                    atr_tp_mult=params["atr_tp_mult"],
                )
                if m["num_trades"] >= 10 and m["profit_factor"] >= 1.0:
                    asset_scores.append(_composite_score(m))
            if asset_scores:
                results.append({**params, "in_sample_score": round(sum(asset_scores) / len(asset_scores), 4), "asset_metrics": {}, "assets_passed": len(asset_scores)})

    if not results:
        print("FAILED: Still no valid results. Using default parameters.")
        best = {"ema_fast": 9, "ema_slow": 21, "rsi_buy_max": 65,
                "atr_sl_mult": 1.5, "atr_tp_mult": 3.0}
        _save_config(best, {}, {}, {"reason": "no_valid_combo"})
        return best

    # ── Sort by in-sample score and take shortlist ──
    results.sort(key=lambda x: x["in_sample_score"], reverse=True)
    shortlist = results[:12]

    # ── Walk-forward out-of-sample validation ──
    print(f"\n{len(results)} combos passed pass-1. Walk-forward validating top {len(shortlist)}...")
    finalists = []
    for r in shortlist:
        per_asset_oos = {}
        oos_scores = []
        oos_trade_counts = []

        for sym, df in datasets.items():
            windows = _walk_forward_slices(len(df))
            if len(windows) < 2:
                continue
            avg_oos, raw_oos = _evaluate_on_walk_forward(df, r, windows)
            if not avg_oos:
                continue
            per_asset_oos[sym] = {
                "avg": avg_oos,
                "windows": len(raw_oos),
            }
            oos_scores.append(_composite_score(avg_oos))
            oos_trade_counts.append(avg_oos.get("num_trades", 0))

        if not oos_scores:
            continue

        oos_score = round(sum(oos_scores) / len(oos_scores), 4)
        avg_oos_trades = round(sum(oos_trade_counts) / len(oos_trade_counts), 2) if oos_trade_counts else 0
        stability_penalty = 0.0
        if len(oos_scores) > 1:
            stability_penalty = min(statistics.pstdev(oos_scores), 0.15)
        final_score = round(oos_score - stability_penalty, 4)

        if avg_oos_trades >= 8 and oos_score >= 0.35:
            finalists.append({
                **r,
                "oos_score": oos_score,
                "stability_penalty": round(stability_penalty, 4),
                "final_score": final_score,
                "oos_metrics_by_asset": per_asset_oos,
                "avg_oos_trades": avg_oos_trades,
            })

    if not finalists:
        print("[!] No finalist passed walk-forward guard. Falling back to top in-sample candidate.")
        fallback = shortlist[0]
        best = fallback
        best_test = {}
        validation_meta = {"mode": "fallback_in_sample", "assets": list(datasets.keys())}
    else:
        finalists.sort(key=lambda x: x["final_score"], reverse=True)
        best = finalists[0]
        best_test = {
            "oos_score": best["oos_score"],
            "stability_penalty": best["stability_penalty"],
            "final_score": best["final_score"],
            "avg_oos_trades": best["avg_oos_trades"],
            "oos_metrics_by_asset": best["oos_metrics_by_asset"],
        }
        validation_meta = {
            "mode": "walk_forward",
            "assets": list(datasets.keys()),
            "shortlist_size": len(shortlist),
            "finalists": len(finalists),
        }

    # ── Save to config ──
    params_only = {
        "ema_fast": best["ema_fast"],
        "ema_slow": best["ema_slow"],
        "rsi_buy_max": best["rsi_buy_max"],
        "atr_sl_mult": best["atr_sl_mult"],
        "atr_tp_mult": best["atr_tp_mult"],
    }
    # Aggregate train metrics from all assets for dashboard history compatibility.
    train_metrics_raw = []
    for m in best.get("asset_metrics", {}).values():
        if isinstance(m, dict):
            train_metrics_raw.append(m)
    train_metrics = _aggregate_metrics(train_metrics_raw) if train_metrics_raw else {}
    train_metrics["score"] = best.get("in_sample_score", 0)
    train_metrics["assets_passed"] = best.get("assets_passed", 0)

    _save_config(params_only, train_metrics, best_test if best_test else {}, validation_meta)

    # ── Print results ──
    print("\n=== OPTIMIZATION COMPLETE ===")
    print(f"  Best EMA Fast    : {best['ema_fast']}")
    print(f"  Best EMA Slow    : {best['ema_slow']}")
    print(f"  RSI Buy Max      : {best['rsi_buy_max']}")
    print(f"  ATR SL Multiplier: {best['atr_sl_mult']}")
    print(f"  ATR TP Multiplier: {best['atr_tp_mult']}")
    print(f"  In-sample score  : {best.get('in_sample_score', 0)}")
    if best_test:
        print(f"  OOS score        : {best_test.get('oos_score', 0)}")
        print(f"  Stability penalty: {best_test.get('stability_penalty', 0)}")
        print(f"  Final score      : {best_test.get('final_score', 0)}")
    print(f"  Combos Tested    : {len(valid_combos)}")
    print(f"  Combos Passed    : {len(results)}")
    if validation_meta.get("mode") == "walk_forward":
        print(f"  Finalists (WF)   : {validation_meta.get('finalists', 0)}")

    return params_only


def _save_config(params, train_metrics, test_metrics, validation_meta):
    """Save best parameters and append to optimization history."""
    # Load existing config
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
    else:
        config = {"history": []}

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    config["best_params"] = params
    config["train_metrics"] = train_metrics
    config["test_metrics"] = test_metrics
    config["last_optimized"] = timestamp
    config["filters"] = FILTERS
    config["validation"] = validation_meta

    # Append to version history
    config.setdefault("history", [])
    config["history"].append({
        "timestamp": timestamp,
        "params": params,
        "train_metrics": train_metrics,
        "test_metrics": test_metrics,
        "validation": validation_meta,
    })

    import math

    def _sanitize(obj):
        """Replace Infinity/NaN with JSON-safe values."""
        if isinstance(obj, dict):
            return {k: _sanitize(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_sanitize(v) for v in obj]
        if isinstance(obj, float):
            if math.isinf(obj):
                return 9999
            if math.isnan(obj):
                return 0
        return obj

    with open(CONFIG_FILE, "w") as f:
        json.dump(_sanitize(config), f, indent=2)

    print(f"\nConfig saved to {CONFIG_FILE}")


# ── Standalone run ───────────────────────────────────────────

if __name__ == "__main__":
    optimize()
