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

    params = f"symbol={symbol}&side={side}&type=MARKET&quantity={quantity}&timestamp={timestamp}"

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

    return r.json()
