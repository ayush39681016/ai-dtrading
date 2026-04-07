"""
app.py — AI Trading System Command Center
Premium black dark-mode dashboard with multi-asset analytics.
"""

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import json
import os
import subprocess
import sys
import requests

from performance import calculate_performance
import executor

# ── Page config ──────────────────────────────────────────────
st.set_page_config(
    page_title="AI Trading System",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Black dark-mode CSS ──────────────────────────────────────
st.markdown("""
<style>
    @keyframes neonPulse {
        0% { box-shadow: 0 0 0 rgba(0, 176, 255, 0.0); }
        50% { box-shadow: 0 0 28px rgba(0, 176, 255, 0.28); }
        100% { box-shadow: 0 0 0 rgba(0, 176, 255, 0.0); }
    }

    .stApp {
        background:
            radial-gradient(circle at 10% 10%, rgba(0, 176, 255, 0.14), transparent 28%),
            radial-gradient(circle at 90% 0%, rgba(139, 92, 246, 0.16), transparent 26%),
            linear-gradient(180deg, #05060a 0%, #04050a 55%, #030409 100%) !important;
    }
    .block-container {
        padding-top: 1.2rem !important;
        padding-bottom: 1.5rem !important;
    }
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0b0f1a 0%, #090b14 100%) !important;
        border-right: 1px solid #1f2a44;
        box-shadow: 0 0 30px rgba(0, 176, 255, 0.08);
    }
    header[data-testid="stHeader"] { background-color: #05060a !important; }

    [data-testid="stMetric"] {
        background: linear-gradient(160deg, rgba(15, 20, 35, 0.9), rgba(10, 13, 24, 0.86));
        border: 1px solid #253659;
        border-radius: 14px;
        padding: 18px 14px;
        box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.03), 0 8px 24px rgba(0, 0, 0, 0.35);
        transition: border-color 0.3s, transform 0.2s;
    }
    [data-testid="stMetric"]:hover {
        border-color: #3cc4ff;
        transform: translateY(-2px);
    }
    [data-testid="stMetricLabel"] {
        color: #8fa4cb !important; font-size: 0.78rem !important;
        text-transform: uppercase; letter-spacing: 0.06em;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.6rem !important; font-weight: 700 !important;
        color: #eaf2ff !important;
    }

    h1, h2, h3, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
        color: #f4f8ff !important;
        letter-spacing: 0.015em;
    }
    p, span, label, .stMarkdown, .stText { color: #bfd0f3 !important; }
    hr { border-color: #1b2844 !important; }

    .stButton > button {
        background: linear-gradient(135deg, #00b0ff, #6c5ce7 70%) !important;
        color: #f8fbff !important;
        font-weight: 700 !important;
        border: 1px solid #4fc8ff !important;
        border-radius: 12px !important;
        padding: 0.6rem 1.4rem !important;
        box-shadow: 0 8px 22px rgba(0, 176, 255, 0.25);
        transition: transform 0.2s, box-shadow 0.2s, filter 0.2s;
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 28px rgba(108, 92, 231, 0.35);
        filter: brightness(1.06);
    }
    .stButton > button:focus-visible {
        outline: 2px solid #7fd4ff !important;
        outline-offset: 2px;
        animation: neonPulse 1.4s ease-in-out infinite;
    }

    .stDataFrame {
        border-radius: 12px;
        overflow: hidden;
        border: 1px solid #253659;
    }

    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        background: #0c1324 !important;
        border-radius: 10px !important;
        color: #97abd1 !important;
        border: 1px solid #223354 !important;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, rgba(0, 176, 255, 0.2), rgba(108, 92, 231, 0.2)) !important;
        color: #7fd4ff !important;
        border-color: #48bfff !important;
        box-shadow: 0 0 18px rgba(0, 176, 255, 0.2);
        animation: neonPulse 2.2s ease-in-out infinite;
    }
    .stAlert {
        background: linear-gradient(160deg, rgba(12, 19, 36, 0.95), rgba(10, 14, 26, 0.95)) !important;
        border: 1px solid #243659 !important;
        border-radius: 12px;
    }

    /* Asset selector pills */
    .stRadio > div { flex-direction: row !important; gap: 12px; }
    .stRadio label {
        background: #0c1324 !important;
        border: 1px solid #223354;
        border-radius: 10px; padding: 8px 18px; cursor: pointer;
    }
    [data-testid="stCodeBlock"] {
        border: 1px solid #29426e !important;
        border-radius: 10px !important;
    }
</style>
""", unsafe_allow_html=True)

ASSET_MAP = {
    "₿ Bitcoin (BTC)": "BTCUSDT",
    "🥇 Gold (XAU)": "XAUUSDT",
    "🥈 Silver (XAG)": "XAGUSDT",
    "📊 All Assets": "ALL",
}

# ── Config is loaded after asset selector below ──────────────
config = {}
if os.path.exists("config.json"):
    with open("config.json", "r") as f:
        config = json.load(f)

params = config.get("best_params", {})
validation = config.get("validation", {})
test_metrics = config.get("test_metrics", {})
runtime = config.get("runtime", {})
RUNTIME_DEFAULTS = {
    "risk_profile": "Balanced",
    "exchange_mode": "demo",
    "fail_safe_mode": "A_hard_stop",
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
STATUS_FILE = "runtime_status.json"


def _load_runtime_status():
    if os.path.exists(STATUS_FILE):
        try:
            with open(STATUS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

# ── Sidebar ──────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚡ System Control")
    st.markdown("---")

    st.markdown("### 🧠 Active Strategy")
    if params:
        st.code(
            f"EMA Fast    : {params.get('ema_fast', '—')}\n"
            f"EMA Slow    : {params.get('ema_slow', '—')}\n"
            f"RSI Buy Max : {params.get('rsi_buy_max', '—')}\n"
            f"ATR SL Mult : {params.get('atr_sl_mult', '—')}\n"
            f"ATR TP Mult : {params.get('atr_tp_mult', '—')}",
            language="yaml",
        )
    else:
        st.info("No optimised params yet.")

    st.markdown("---")
    st.markdown(f"**Last Optimised:** {config.get('last_optimized', 'Never')}")
    st.markdown(f"**Strategy Versions:** {len(config.get('history', []))}")

    st.markdown("---")
    st.markdown("### 🎛️ Risk Profile")
    current_profile = runtime.get("risk_profile", RUNTIME_DEFAULTS["risk_profile"])
    profile_idx = ["Conservative", "Balanced", "Aggressive"].index(current_profile) if current_profile in ["Conservative", "Balanced", "Aggressive"] else 1
    selected_profile = st.selectbox(
        "Profile",
        ["Conservative", "Balanced", "Aggressive"],
        index=profile_idx,
        label_visibility="collapsed",
    )
    profile_presets = {
        "Conservative": {"risk_per_trade_pct": 0.0025, "max_daily_loss_usd": 25.0, "max_open_positions": 1},
        "Balanced": {"risk_per_trade_pct": 0.0050, "max_daily_loss_usd": 50.0, "max_open_positions": 2},
        "Aggressive": {"risk_per_trade_pct": 0.0100, "max_daily_loss_usd": 100.0, "max_open_positions": 3},
    }
    preview = profile_presets[selected_profile]
    st.caption(
        f"Risk/trade: {preview['risk_per_trade_pct']*100:.2f}%  ·  "
        f"Daily stop: ${preview['max_daily_loss_usd']:.0f}  ·  "
        f"Max open: {preview['max_open_positions']}"
    )
    if st.button("💾 Save Risk Profile", use_container_width=True):
        runtime_cfg = {**RUNTIME_DEFAULTS, **runtime, **profile_presets[selected_profile]}
        runtime_cfg["risk_profile"] = selected_profile
        config["runtime"] = runtime_cfg
        with open("config.json", "w") as f:
            json.dump(config, f, indent=2)
        st.success("Risk profile saved. Restart strategy engine to apply.")

    with st.expander("Advanced Runtime Settings", expanded=False):
        base_runtime = {**RUNTIME_DEFAULTS, **runtime}
        exchange_mode_val = st.selectbox(
            "Exchange mode",
            ["demo", "testnet"],
            index=0 if str(base_runtime.get("exchange_mode", "demo")) == "demo" else 1,
        )
        fail_safe_val = st.selectbox(
            "Fail-safe mode",
            ["A_hard_stop", "B_internal_paper_fallback", "C_retry_then_stop"],
            index=["A_hard_stop", "B_internal_paper_fallback", "C_retry_then_stop"].index(
                str(base_runtime.get("fail_safe_mode", "A_hard_stop"))
            ) if str(base_runtime.get("fail_safe_mode", "A_hard_stop")) in ["A_hard_stop", "B_internal_paper_fallback", "C_retry_then_stop"] else 0,
        )
        fee_bps_val = st.number_input("Fee (bps)", min_value=0.0, max_value=50.0, value=float(base_runtime["fee_bps"]), step=0.5)
        slippage_bps_val = st.number_input("Slippage (bps)", min_value=0.0, max_value=50.0, value=float(base_runtime["slippage_bps"]), step=0.5)
        risk_pct_val = st.number_input(
            "Risk per trade (%)",
            min_value=0.05,
            max_value=5.0,
            value=float(base_runtime["risk_per_trade_pct"] * 100),
            step=0.05,
        )
        daily_loss_val = st.number_input("Max daily loss ($)", min_value=5.0, max_value=10000.0, value=float(base_runtime["max_daily_loss_usd"]), step=5.0)
        cooldown_val = st.number_input("Cooldown (minutes)", min_value=1, max_value=1440, value=int(base_runtime["cooldown_minutes"]), step=1)
        retry_attempts_val = st.number_input("Retry attempts (mode C)", min_value=1, max_value=50, value=int(base_runtime["retry_attempts"]), step=1)
        retry_interval_val = st.number_input("Retry interval sec (mode C)", min_value=1, max_value=300, value=int(base_runtime["retry_interval_sec"]), step=1)
        cooldown_after_stop_val = st.number_input(
            "Cooldown after stop min (mode C)",
            min_value=1,
            max_value=1440,
            value=int(base_runtime["cooldown_after_stop_min"]),
            step=1,
        )
        consec_loss_val = st.number_input("Max consecutive losses", min_value=1, max_value=20, value=int(base_runtime["max_consecutive_losses"]), step=1)
        open_pos_val = st.number_input("Max open positions", min_value=1, max_value=10, value=int(base_runtime["max_open_positions"]), step=1)
        mock_streak_val = st.number_input("Max mock orders streak", min_value=1, max_value=20, value=int(base_runtime["max_mock_orders_streak"]), step=1)

        if st.button("🛠️ Save Advanced Runtime", use_container_width=True):
            runtime_cfg = {**base_runtime}
            runtime_cfg.update({
                "exchange_mode": exchange_mode_val,
                "fail_safe_mode": fail_safe_val,
                "fee_bps": float(fee_bps_val),
                "slippage_bps": float(slippage_bps_val),
                "risk_per_trade_pct": float(risk_pct_val) / 100.0,
                "max_daily_loss_usd": float(daily_loss_val),
                "cooldown_minutes": int(cooldown_val),
                "retry_attempts": int(retry_attempts_val),
                "retry_interval_sec": int(retry_interval_val),
                "cooldown_after_stop_min": int(cooldown_after_stop_val),
                "max_consecutive_losses": int(consec_loss_val),
                "max_open_positions": int(open_pos_val),
                "max_mock_orders_streak": int(mock_streak_val),
            })
            config["runtime"] = runtime_cfg
            with open("config.json", "w") as f:
                json.dump(config, f, indent=2)
            st.success("Advanced runtime settings saved. Restart strategy engine to apply.")

    # Cache status
    st.markdown("---")
    st.markdown("### 📡 Live Monitor")
    rt = _load_runtime_status()
    health = executor.get_connection_health()
    st.caption(
        f"Engine: {rt.get('engine_state', 'unknown')}  ·  "
        f"Exchange: {(runtime.get('exchange_mode') or 'demo')}  ·  "
        f"Fail-safe: {(runtime.get('fail_safe_mode') or 'A_hard_stop')}"
    )
    st.caption(
        f"Conn: {health.get('status', 'unknown')}  ·  "
        f"Kill-switch: {rt.get('kill_switch', False)}  ·  "
        f"Cooldown: {rt.get('cooldown_until', 'none')}"
    )

    st.markdown("---")
    st.markdown("### 💾 Data Cache")
    cache_dir = os.path.join(os.path.dirname(__file__) or ".", "data_cache")
    if os.path.exists(cache_dir):
        cached_files = [f for f in os.listdir(cache_dir) if f.endswith(".csv")]
        st.success(f"{len(cached_files)} assets cached locally")
    else:
        st.warning("No cache yet — click Sync below")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🧠 AI Power-Up", use_container_width=True):
            with st.spinner("Optimizing from cache..."):
                result = subprocess.run(
                    [sys.executable, "optimizer.py"],
                    capture_output=True, text=True,
                    cwd=os.path.dirname(__file__) or "."
                )
                st.text(result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout)
                if result.returncode == 0:
                    st.success("✅ Power-up complete! Refresh page.")
                else:
                    st.error(f"Error:\n{result.stderr[-500:]}")

    with col2:
        if st.button("⚡ Sync Data Vault", use_container_width=True):
            with st.spinner("Downloading fresh data..."):
                result = subprocess.run(
                    [sys.executable, "data_cache.py"],
                    capture_output=True, text=True,
                    cwd=os.path.dirname(__file__) or "."
                )
                st.text(result.stdout[-1000:] if len(result.stdout) > 1000 else result.stdout)
                if result.returncode == 0:
                    st.success("✅ Data vault synced!")

    st.markdown("---")
    st.caption("Powered by Python · Bybit API · Streamlit")


# ── Live Data Helpers ────────────────────────────────────────

def get_live_prices():
    """Fetch latest prices from Bybit MAINNET for accurate context."""
    prices = {"BTCUSDT": 0, "XAUUSDT": 0, "XAGUSDT": 0}
    try:
        # Using Mainnet Public API for Accurate Displays (No Key Needed)
        for sym in prices.keys():
            url = f"https://api.bybit.com/v5/market/tickers?category=linear&symbol={sym}"
            res = requests.get(url, timeout=5).json()
            if res.get("retCode") == 0 and res["result"]["list"]:
                prices[sym] = float(res["result"]["list"][0]["lastPrice"])
    except Exception:
        pass
    return prices

# ── Asset Selector ───────────────────────────────────────────
st.markdown(
    "<h1 style='margin-bottom:0'>⚡ AI Trading System</h1>"
    "<p style='color:#555; margin-top:4px; font-size:0.95rem;'>"
    "Multi-asset self-improving engine  ·  BTC + Gold + Silver  ·  EMA + RSI + Volume + ATR</p>",
    unsafe_allow_html=True,
)

# ── Live Tickers ─────────────────────────────────────────────
live_prices = get_live_prices()
t1, t2, t3, _ = st.columns([1, 1, 1, 3])
with t1:
    st.markdown(f"**₿ BTC:** `${live_prices['BTCUSDT']:,.2f}`")
with t2:
    st.markdown(f"**🥇 Gold:** `${live_prices['XAUUSDT']:,.2f}`")
with t3:
    st.markdown(f"**🥈 Silver:** `${live_prices['XAGUSDT']:,.2f}`")

st.info(
    "💡 **Note:** Tickers above reflect **Real-World Mainnet** prices for your context. "
    f"The trading engine executes on **Bybit {str(runtime.get('exchange_mode', 'demo')).capitalize()}** mode, "
    "so execution prices and fills may differ from public tickers."
)

selected_label = st.radio(
    "Select Asset", list(ASSET_MAP.keys()),
    horizontal=True, label_visibility="collapsed"
)
selected_symbol = ASSET_MAP[selected_label]

# ── Load data (Filtered by selection) ───────────────────────
metrics = calculate_performance(selected_symbol)
config = {}
if os.path.exists("config.json"):
    with open("config.json", "r") as f:
        config = json.load(f)

params = config.get("best_params", {})

# ── Metrics row ──────────────────────────────────────────────
st.markdown("---")
c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("💰 Profit", f"${metrics['total_profit']:,.2f}")
c2.metric("🎯 Win Rate", f"{metrics['win_rate']:.1f}%")
pf_val = metrics["profit_factor"]
c3.metric("🔥 Profit Factor", f"{pf_val:.2f}" if pf_val != float("inf") else "∞")
c4.metric("📉 Max Drawdown", f"{metrics['max_drawdown']:.1f}%")
c5.metric("📊 Sharpe Ratio", f"{metrics['sharpe']:.2f}")
c6.metric("🔢 Trades", metrics["num_trades"])

# ── Go-Live Readiness Gate ───────────────────────────────────
st.markdown("---")
st.markdown("### 🛡️ Go-Live Readiness")

readiness_checks = [
    ("Profit Factor >= 1.20", metrics.get("profit_factor", 0) >= 1.20),
    ("Win Rate >= 45%", metrics.get("win_rate", 0) >= 45),
    ("Max Drawdown <= 25%", metrics.get("max_drawdown", 1000) <= 25),
    ("Real Trades >= 30", metrics.get("real_trades", 0) >= 30),
    ("Mock Trades = 0", metrics.get("mock_trades", 0) == 0),
    ("Optimizer Validation: walk_forward", validation.get("mode") == "walk_forward"),
]
ready_now = all(ok for _, ok in readiness_checks)

if ready_now:
    st.success("✅ READY FOR SMALL LIVE PILOT (size up slowly).")
else:
    st.warning("⚠️ NOT READY FOR LIVE CAPITAL YET.")

rc1, rc2 = st.columns(2)
with rc1:
    for label, ok in readiness_checks[:3]:
        st.markdown(f"{'✅' if ok else '❌'} {label}")
with rc2:
    for label, ok in readiness_checks[3:]:
        st.markdown(f"{'✅' if ok else '❌'} {label}")

st.caption(
    f"Real trades: {metrics.get('real_trades', 0)}  ·  "
    f"Mock trades: {metrics.get('mock_trades', 0)}  ·  "
    f"Validation mode: {validation.get('mode', 'n/a')}  ·  "
    f"Risk profile: {runtime.get('risk_profile', RUNTIME_DEFAULTS['risk_profile'])}"
)


# ── Instant Backtest Panel ───────────────────────────────────
st.markdown("---")
st.markdown("### ⚡ Instant Backtest (from cached data)")

bt_cols = st.columns(3)
for i, (label, sym) in enumerate([("₿ BTCUSDT", "BTCUSDT"), ("🥇 XAUUSDT", "XAUUSDT"), ("🥈 XAGUSDT", "XAGUSDT")]):
    with bt_cols[i]:
        cache_path = os.path.join(cache_dir, f"{sym}_60.csv")
        if os.path.exists(cache_path):
            try:
                from backtester import run_backtest
                cached_df = pd.read_csv(cache_path)
                bt_result = run_backtest(
                    cached_df,
                    ema_fast=params.get("ema_fast", 9),
                    ema_slow=params.get("ema_slow", 21),
                    rsi_buy_max=params.get("rsi_buy_max", 65),
                    atr_sl_mult=params.get("atr_sl_mult", 1.5),
                    atr_tp_mult=params.get("atr_tp_mult", 3.0),
                )
                profit_color = "#00b0ff" if bt_result["total_profit"] >= 0 else "#ff5252"
                st.markdown(
                    f"<div style='background:linear-gradient(160deg, rgba(15,20,35,0.92), rgba(10,13,24,0.88)); "
                    f"border:1px solid #253659; border-radius:14px; padding:16px; text-align:center; "
                    f"box-shadow:0 8px 24px rgba(0,0,0,0.3);'>"
                    f"<h3 style='margin:0; color:#fff;'>{label}</h3>"
                    f"<p style='font-size:1.8rem; font-weight:700; color:{profit_color}; margin:8px 0;'>"
                    f"${bt_result['total_profit']:,.2f}</p>"
                    f"<p style='color:#9db4df; font-size:0.85rem;'>"
                    f"WR: {bt_result['win_rate']:.0f}%  ·  PF: {bt_result['profit_factor']:.1f}  ·  "
                    f"Trades: {bt_result['num_trades']}</p>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
            except Exception as e:
                st.warning(f"{label}: {e}")
        else:
            st.info(f"{label}: No cache. Click ⚡ Sync Data Vault.")


# ── Chart styling helper ─────────────────────────────────────

def _dark_chart(figsize=(12, 4)):
    fig, ax = plt.subplots(figsize=figsize)
    fig.patch.set_facecolor("#070b14")
    ax.set_facecolor("#0b1120")
    ax.tick_params(colors="#91abd7")
    ax.xaxis.label.set_color("#9cb5df")
    ax.yaxis.label.set_color("#9cb5df")
    ax.title.set_color("#edf4ff")
    for spine in ax.spines.values():
        spine.set_color("#223a62")
        spine.set_alpha(0.45)
    ax.grid(True, linestyle="--", alpha=0.18, color="#2a4472")
    return fig, ax


# ── Tabs ─────────────────────────────────────────────────────
st.markdown("---")
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📈 Equity Curve", "📅 Monthly Returns", "📜 Trade Log", "🕰️ Optimization History", "🟢 Live Trading Monitor"])

with tab1:
    eq = metrics["equity_curve"]
    if eq:
        fig, ax = _dark_chart()
        color = "#00b0ff" if eq[-1] >= 0 else "#ff5252"
        ax.fill_between(range(1, len(eq) + 1), eq, alpha=0.08, color=color)
        ax.plot(range(1, len(eq) + 1), eq, color=color, linewidth=2, marker="o", markersize=4)
        ax.axhline(y=0, color="#2b4778", linewidth=0.7, linestyle="--")
        ax.set_xlabel("Completed Trades")
        ax.set_ylabel("Cumulative Profit ($)")
        ax.set_title("Equity Curve")
        ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("$%.0f"))
        st.pyplot(fig)
    else:
        st.info("⏳ Waiting for completed BUY → SELL pairs...")

with tab2:
    monthly = metrics.get("monthly_returns", {})
    if monthly:
        months = list(monthly.keys())
        values = list(monthly.values())
        colors = ["#00b0ff" if v >= 0 else "#ff5252" for v in values]
        fig, ax = _dark_chart(figsize=(12, 4))
        bars = ax.bar(months, values, color=colors, width=0.6, edgecolor="none")
        ax.axhline(y=0, color="#2b4778", linewidth=0.7)
        ax.set_title("Monthly Returns")
        ax.set_ylabel("Profit ($)")
        for bar, val in zip(bars, values):
            ax.text(
                bar.get_x() + bar.get_width() / 2, bar.get_height(),
                f"${val:,.0f}", ha="center", va="bottom" if val >= 0 else "top",
                color="#c7d8f5", fontsize=9,
            )
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()
        st.pyplot(fig)
    else:
        st.info("⏳ No monthly data yet...")

with tab3:
    trade_list = metrics.get("trades", [])
    if trade_list:
        log_df = pd.DataFrame(trade_list)
        display_cols = ["symbol", "entry_time", "exit_time", "entry_price", "exit_price", "pnl"]
        log_df = log_df[[c for c in display_cols if c in log_df.columns]].copy()
        if "pnl" in log_df.columns:
            log_df["pnl"] = log_df["pnl"].apply(lambda x: f"${x:+,.2f}")
        log_df.columns = ["Asset", "Entry Time", "Exit Time", "Entry $", "Exit $", "PnL"][:len(log_df.columns)]
        st.dataframe(log_df, use_container_width=True, hide_index=True)
    else:
        file_path = "trades.csv"
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            raw = pd.read_csv(
                file_path,
                names=["Time", "Asset", "Signal", "Price", "Version", "Qty", "Order ID", "Mock", "Fee bps", "Slippage bps"],
                on_bad_lines="skip",
            )
            st.dataframe(raw, use_container_width=True, hide_index=True)
        else:
            st.warning("No LIVE trades recorded yet (BUY -> SELL pairs). Start the strategy engine.")

with tab4:
    history = config.get("history", [])
    st.markdown("#### Optimizer Validation Snapshot")
    oos_score = test_metrics.get("oos_score", "n/a")
    stability = test_metrics.get("stability_penalty", "n/a")
    final_score = test_metrics.get("final_score", "n/a")
    avg_oos_trades = test_metrics.get("avg_oos_trades", "n/a")
    st.info(
        f"Mode: {validation.get('mode', 'n/a')}  |  "
        f"OOS Score: {oos_score}  |  Stability Penalty: {stability}  |  "
        f"Final Score: {final_score}  |  Avg OOS Trades: {avg_oos_trades}"
    )
    if history:
        rows = []
        for h in history:
            p = h.get("params", {})
            tm = h.get("train_metrics", {})
            vm = h.get("validation", {})
            rows.append({
                "Date": h.get("timestamp", ""),
                "EMA": f"{p.get('ema_fast','?')}/{p.get('ema_slow','?')}",
                "RSI Max": p.get("rsi_buy_max", ""),
                "ATR SL": p.get("atr_sl_mult", ""),
                "ATR TP": p.get("atr_tp_mult", ""),
                "Profit Factor": tm.get("profit_factor", ""),
                "Win Rate": f"{tm.get('win_rate', '')}%",
                "Score": tm.get("score", ""),
                "Validation": vm.get("mode", ""),
            })
        hist_df = pd.DataFrame(rows)
        st.dataframe(hist_df, use_container_width=True, hide_index=True)
    else:
        st.info("No optimization runs yet. Click '🧠 AI Power-Up' in the sidebar.")

with tab5:
    rt = _load_runtime_status()
    health = executor.check_connection()

    st.markdown("### Runtime State")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Engine", rt.get("engine_state", "unknown"))
    m2.metric("Exchange", rt.get("exchange_mode", runtime.get("exchange_mode", "demo")))
    m3.metric("Fail-safe", rt.get("fail_safe_mode", runtime.get("fail_safe_mode", "A_hard_stop")))
    m4.metric("Connectivity", health.get("status", "unknown"))

    st.markdown("---")
    st.markdown("### Connection Health")
    st.json(health)

    st.markdown("---")
    st.markdown("### Signal/Position Snapshot")
    signal_rows = []
    for sym, data in rt.get("last_signal", {}).items():
        pos = rt.get("positions", {}).get(sym, {})
        signal_rows.append({
            "Symbol": sym,
            "Signal": data.get("signal"),
            "Price": data.get("price"),
            "ATR": data.get("atr"),
            "Position Active": pos.get("active", False),
            "Entry": pos.get("entry", 0),
            "SL": pos.get("sl", 0),
            "TP": pos.get("tp", 0),
            "Qty": pos.get("qty", 0),
        })
    if signal_rows:
        st.dataframe(pd.DataFrame(signal_rows), use_container_width=True, hide_index=True)
    else:
        st.info("No runtime snapshot yet. Start strategy_engine.py.")

    st.markdown("---")
    st.markdown("### Last Order / Event Trail")
    if rt.get("last_order"):
        st.json(rt.get("last_order"))
    if rt.get("events"):
        st.dataframe(pd.DataFrame(rt.get("events")), use_container_width=True, hide_index=True)

# ── Footer ───────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    "<p style='text-align:center; color:#333; font-size:0.8rem;'>"
    "⚡ Self-Improving Trading System  ·  BTC + Gold + Silver  ·  EMA + RSI + Volume + ATR  ·  "
    f"Max Consecutive Losses: {metrics.get('max_consecutive_losses', 0)}"
    "</p>",
    unsafe_allow_html=True,
)