import requests

BASE = "https://api.mexc.com"


def get_price(symbol):

    try:

        url = f"{BASE}/api/v3/ticker/bookTicker?symbol={symbol}"

        data = requests.get(url).json()

        return {
            "bid": float(data["bidPrice"]),
            "ask": float(data["askPrice"])
        }

    except:

        return None
