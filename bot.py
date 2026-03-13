import ccxt
import time
import os

print("Bot iniciado...")

exchange = ccxt.mexc({
    "enableRateLimit": True
})

symbol = "BTC/USDT"

while True:

    try:

        ticker = exchange.fetch_ticker(symbol)

        price = ticker["last"]

        print("Preço BTC:", price)

    except Exception as e:
        print("Erro:", e)

    time.sleep(10)
