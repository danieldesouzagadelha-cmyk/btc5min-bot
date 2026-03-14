import time
import traceback

from simulator import trade
from mercado import get_market_data

print("===================================")
print("     LIQUIDITY REVERSION BOT       ")
print("===================================")

loop = 0

while True:

    try:

        loop += 1
        print("\nLoop:", loop)

        price, bid, ask, bid_volume, ask_volume = get_market_data()

        print("Preço:", price)
        print("Bid:", bid)
        print("Ask:", ask)

        trade(price, bid, ask, bid_volume, ask_volume)

        time.sleep(1)

    except Exception as e:

        print("ERRO:", e)
        traceback.print_exc()

        time.sleep(5)
