import time

from exchange import get_market
from strategy import detect_reversion
from simulator import trade

print("Liquidity Reversion Bot iniciado")

while True:

    try:

        price, bids, asks, best_bid, best_ask = get_market()

        print("Preço:", price)

        signal = detect_reversion(price, bids)

        if signal:
            print("Reversão detectada")
            trade(price)

    except Exception as e:

        print("Erro:", e)

    time.sleep(5)
