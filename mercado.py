import requests

def get_price():

    url = "https://api.mexc.com/api/v3/ticker/price?symbol=BTCUSDT"

    data = requests.get(url).json()

    price = float(data["price"])

    return price
