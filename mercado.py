import requests

def get_price(symbol):

    url = f"https://api.mexc.com/api/v3/ticker/price?symbol={symbol}"

    data = requests.get(url).json()

    price = float(data["price"])

    return price
