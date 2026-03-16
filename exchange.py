import time
import hmac
import hashlib
import requests
import os

API_KEY = os.getenv("MEXC_API_KEY")
SECRET = os.getenv("MEXC_SECRET")

BASE = "https://api.mexc.com"


def create_order(symbol, side, quantity):

    endpoint = "/api/v3/order"
    timestamp = int(time.time() * 1000)

    # BUY usa quoteOrderQty (valor em USDT)
    if side == "BUY":
        params = f"symbol={symbol}&side=BUY&type=MARKET&quoteOrderQty={quantity}&timestamp={timestamp}"
    else:
        params = f"symbol={symbol}&side=SELL&type=MARKET&quantity={quantity}&timestamp={timestamp}"

    signature = hmac.new(
        SECRET.encode(),
        params.encode(),
        hashlib.sha256
    ).hexdigest()

    url = f"{BASE}{endpoint}?{params}&signature={signature}"

    headers = {
        "X-MEXC-APIKEY": API_KEY
    }

    r = requests.post(url, headers=headers)

    response = r.json()

    print("MEXC ORDER RESPONSE:", response)

    return response
