import hmac, hashlib, time, requests, os, urllib.parse
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("BYBIT_API_KEY", "")
API_SECRET = os.getenv("BYBIT_API_SECRET", "")
BASE_URL = "https://api-testnet.bybit.com"

print(f"Key: {API_KEY}")

ts_res = requests.get(BASE_URL + "/v5/market/time").json()
server_time = int(ts_res["result"]["timeNano"]) // 1000000
timestamp = str(server_time)

payload = "accountType=UNIFIED&coin=USDT"
param_str = timestamp + API_KEY + "5000" + payload
hash_code = hmac.new(bytes(API_SECRET, "utf-8"), param_str.encode("utf-8"), hashlib.sha256).hexdigest()

headers = {
    'X-BAPI-API-KEY': API_KEY,
    'X-BAPI-SIGN': hash_code,
    'X-BAPI-SIGN-TYPE': '2',
    'X-BAPI-TIMESTAMP': timestamp,
    'X-BAPI-RECV-WINDOW': '5000',
    'Content-Type': 'application/json',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

url = f"{BASE_URL}/v5/account/wallet-balance?{payload}"
print(f"Requesting {url}")
res = requests.get(url, headers=headers)
print(f"Status: {res.status_code}")
print(f"Body: {res.text}")
