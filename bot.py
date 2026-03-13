import time

from exchange import get_market
from strategy import detect_reversion
from simulator import trade

print("===================================")
print("  LIQUIDITY REVERSION BOT STARTED  ")
print("===================================")

loop_count = 0

while True:

    try:

        loop_count += 1

        # pegar dados da MEXC
        price, bids, asks, best_bid, best_ask = get_market()

        print("")
        print("Loop:", loop_count)
        print("Preço atual:", price)
        print("Best BID:", best_bid)
        print("Best ASK:", best_ask)

        # detectar reversão de liquidez
        signal = detect_reversion(price, bids)

        if signal:

            print(">>> REVERSÃO DETECTADA <<<")

            trade(price)

        else:

            print("Sem sinal de trade")

    except Exception as e:

        print("ERRO NO BOT:", e)

    # delay
    time.sleep(5)
