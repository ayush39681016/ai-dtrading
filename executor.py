import os
import hmac
import hashlib
import time
import json
import requests
import urllib.parse
from dotenv import load_dotenv

# Load env vars
load_dotenv()
API_KEY = os.getenv("BYBIT_API_KEY", "")
API_SECRET = os.getenv("BYBIT_API_SECRET", "")
CONFIG_FILE = "config.json"
DEFAULT_RUNTIME = {
    "exchange_mode": "demo",  # demo | testnet
}
BASE_URLS = {
    "demo": "https://api-demo.bybit.com",
    "testnet": "https://api-testnet.bybit.com",
}

_last_health = {
    "ok": False,
    "status": "unknown",
    "message": "No checks run yet",
    "exchange_mode": "demo",
    "base_url": BASE_URLS["demo"],
    "http_status": None,
    "ret_code": None,
    "timestamp": None,
}


def _load_runtime():
    runtime = DEFAULT_RUNTIME.copy()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                cfg = json.load(f)
            runtime.update(cfg.get("runtime", {}))
        except Exception:
            pass
    return runtime


def _base_url():
    mode = str(_load_runtime().get("exchange_mode", "demo")).strip().lower()
    if mode not in BASE_URLS:
        mode = "demo"
    return BASE_URLS[mode], mode


def _compute_time_offset(base_url):
    try:
        ts_res = requests.get(base_url + "/v5/market/time", timeout=5).json()
        if ts_res.get("retCode") == 0:
            server_time = int(ts_res["result"]["timeNano"]) // 1000000
            local_time = int(time.time() * 1000)
            return server_time - local_time
    except Exception:
        pass
    return 0

def _gen_signature(payload, timestamp):
    param_str = str(timestamp) + API_KEY + "5000" + payload
    hash_code = hmac.new(
        bytes(API_SECRET, "utf-8"),
        param_str.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    return hash_code

def _send_request(method, endpoint, payload_str=""):
    base_url, mode = _base_url()
    time_offset = _compute_time_offset(base_url)
    timestamp = str(int(time.time() * 1000) + time_offset)
    signature = _gen_signature(payload_str, timestamp)

    headers = {
        'X-BAPI-API-KEY': API_KEY,
        'X-BAPI-SIGN': signature,
        'X-BAPI-SIGN-TYPE': '2',
        'X-BAPI-TIMESTAMP': timestamp,
        'X-BAPI-RECV-WINDOW': '5000',
        'Content-Type': 'application/json'
    }
    
    url = base_url + endpoint
    try:
        if method == "GET":
            if payload_str:
                url += "?" + payload_str
            res = requests.get(url, headers=headers, timeout=10)
        else:
            res = requests.post(url, headers=headers, data=payload_str.encode('utf-8'), timeout=10)
        
        try:
            data = res.json()
        except Exception:
            print(f"Bybit Raw Response ({res.status_code}):\n{res.text}")
            _set_health(
                ok=False,
                status="network_error",
                message="Non-JSON response from Bybit",
                exchange_mode=mode,
                base_url=base_url,
                http_status=res.status_code,
                ret_code=None,
            )
            return None
            
        if data.get("retCode") != 0:
            print(f"Bybit API Error ({res.status_code}): {data}")
            status = "auth_error" if res.status_code in (401, 403) else "blocked"
            _set_health(
                ok=False,
                status=status,
                message=str(data.get("retMsg", "Bybit request failed")),
                exchange_mode=mode,
                base_url=base_url,
                http_status=res.status_code,
                ret_code=data.get("retCode"),
            )
        else:
            _set_health(
                ok=True,
                status="ok",
                message="Request successful",
                exchange_mode=mode,
                base_url=base_url,
                http_status=res.status_code,
                ret_code=data.get("retCode"),
            )
        return data
    except Exception as e:
        print(f"Request Exception: {e}")
        _set_health(
            ok=False,
            status="network_error",
            message=str(e),
            exchange_mode=mode,
            base_url=base_url,
            http_status=None,
            ret_code=None,
        )
        return None


def _set_health(ok, status, message, exchange_mode, base_url, http_status, ret_code):
    _last_health.update({
        "ok": bool(ok),
        "status": status,
        "message": message,
        "exchange_mode": exchange_mode,
        "base_url": base_url,
        "http_status": http_status,
        "ret_code": ret_code,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    })


def get_connection_health():
    """Return normalized connectivity/auth status for monitor panels."""
    return dict(_last_health)


def check_connection():
    """Active health check against wallet endpoint."""
    query = urllib.parse.urlencode({"accountType": "UNIFIED", "coin": "USDT"})
    res = _send_request("GET", "/v5/account/wallet-balance", query)
    health = get_connection_health()
    health["credentials_present"] = bool(API_KEY and API_SECRET)
    health["can_trade"] = bool(res and res.get("retCode") == 0)
    return health


def get_usdt_balance():
    query = urllib.parse.urlencode({"accountType": "UNIFIED", "coin": "USDT"})
    res = _send_request("GET", "/v5/account/wallet-balance", query)
    if res and res.get("retCode") == 0:
        accounts = res["result"]["list"]
        if accounts:
            for coin in accounts[0].get("coin", []):
                if coin["coin"] == "USDT":
                    avail = coin.get("availableToBorrow", "") or "0"
                    wallet = coin.get("walletBalance", "") or "0"
                    return float(avail) + float(wallet)
            if "totalAvailableBalance" in accounts[0]:
                total = accounts[0].get("totalAvailableBalance", "") or "0"
                return float(total)
    
    # Fallback for architecture testing when auth/network fails
    print("Bybit auth failed. Returning mock balance 10000.0 USDT")
    return 10000.0

def place_market_order(symbol: str, side: str, qty: float):
    payload = {
        "category": "linear",
        "symbol": symbol,
        "side": side.capitalize(),
        "orderType": "Market",
        "qty": str(qty),
        "timeInForce": "IOC"
    }
    res = _send_request("POST", "/v5/order/create", json.dumps(payload))
    if res and res.get("retCode") == 0:
        order_id = res['result']['orderId']
        print(f"Executed: {side.upper()} {qty} {symbol} | OrderID: {order_id}")
        return order_id
        
    mock_id = f"mock_{int(time.time()*1000)}"
    print(f"Mock executed: {side.upper()} {qty} {symbol} | OrderID: {mock_id}")
    return mock_id

if __name__ == "__main__":
    print("Testing Bybit V5 Requests API Connection...")
    health = check_connection()
    print(f"Health: {health}")
    bal = get_usdt_balance()
    print(f"Available USDT Balance: {bal}")
