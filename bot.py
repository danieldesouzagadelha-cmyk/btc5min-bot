import time
from mercado import get_price
from strategy import trade

print("===================================")
print("      TREND PULLBACK BOT           ")
print("===================================")

loop = 0

while True:

    loop += 1
    print("Loop:", loop)

    price = get_price()

    trade(price)

    time.sleep(1)
