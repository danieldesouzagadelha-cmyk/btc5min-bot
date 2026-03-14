import requests

def get_price(symbol):

    try:

        url = f"https://api.mexc.com/api/v3/ticker/bookTicker?symbol={symbol}"

        response = requests.get(url, timeout=5)

        data = response.json()

        bid = float(data["bidPrice"])
        ask = float(data["askPrice"])

        # usamos o preço médio entre bid e ask
        price = (bid + ask) / 2

        return price

    except Exception as e:

        print("Erro ao buscar preço:", symbol, e)

        return None
