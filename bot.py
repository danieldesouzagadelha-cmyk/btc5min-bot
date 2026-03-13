import time
import traceback

from exchange import get_market
from strategy import detect_reversion
from simulator import trade

print("===================================")
print("   LIQUIDITY REVERSION BOT START   ")
print("===================================")

loop = 0

while True:

    try:

        loop += 1

        price, bids, asks, best_bid, best_ask = get_market()

        print("")
        print("Loop:", loop)
        print("Preço:", price)
        print("Bid:", best_bid)
        print("Ask:", best_ask)

        signal = detect_reversion(price, bids)

        if signal:

            print("REVERSÃO DETECTADA")

            trade(price)

        else:

            print("Sem trade")

    except Exception as e:

        print("ERRO:", e)
        traceback.print_exc()

    time.sleep(5)
