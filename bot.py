import time
from mercado import get_price
from strategy import trade

pairs = [
"BTCUSDT",
"ETHUSDT",
"SOLUSDT",
"AVAXUSDT"
]

print("===================================")
print(" MULTI COIN TREND PULLBACK BOT ")
print("===================================")

loop = 0

while True:

    loop += 1
    print("Loop:", loop)

    for pair in pairs:

        price = get_price(pair)

        trade(pair, price)

    time.sleep(1)
