import requests

def get_price(symbol):

    try:

        url = f"https://api.mexc.com/api/v3/ticker/price?symbol={symbol}"

        response = requests.get(url, timeout=5)

        data = response.json()

        price = float(data["price"])

        return price

    except Exception as e:

        print("Erro ao buscar preço:", symbol, e)

        return None
