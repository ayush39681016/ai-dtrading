import time
import executor
from strategy_engine import load_params, get_data, log_trade

def force_trade():
    print("[*] Forcing a single BUY trade for testing...\n")

    # 1. Load current strategy parameters
    params = load_params()

    # 2. Get current live price of BTCUSDT
    df = get_data(limit=5)
    current_price = df["close"].iloc[-1]

    # 3. Use the Bybit Executor to place the Market Order
    print("Initiating Bybit Sequence...")
    order_id = executor.place_market_order(symbol="BTCUSDT", side="BUY", qty=0.001)

    # 4. Log the trade seamlessly into the system so the Dashboard registers it
    print(f"Logging trade into engine at Price: ${current_price:.2f}")
    is_mock = str(order_id).startswith("mock_")
    log_trade(
        "BTCUSDT",
        "BUY",
        current_price,
        params,
        qty=0.001,
        order_id=order_id,
        is_mock=is_mock,
        fee_bps=5.0,
        slippage_bps=3.0,
    )

    print("\n[OK] Trade executed and injected into the architecture!")
    print("Check your dashboard to see the new entry pop up!")

if __name__ == "__main__":
    force_trade()
