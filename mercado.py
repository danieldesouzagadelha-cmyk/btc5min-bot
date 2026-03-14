import requests

def get_market_data():

    url = "https://api.mexc.com/api/v3/depth?symbol=BTCUSDT&limit=5"

    response = requests.get(url)
    data = response.json()

    bid = float(data["bids"][0][0])
    ask = float(data["asks"][0][0])

    bid_volume = float(data["bids"][0][1])
    ask_volume = float(data["asks"][0][1])

    price = (bid + ask) / 2

    return price, bid, ask, bid_volume, ask_volume
