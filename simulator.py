import time

capital = 50
btc = 0

position_price = None

last_trade_time = 0
cooldown_seconds = 60

def trade(price):

    global capital
    global btc
    global position_price
    global last_trade_time

    now = time.time()

    # verificar cooldown
    if now - last_trade_time < cooldown_seconds:
        print("Cooldown ativo")
        return

    # BUY
    if btc == 0 and capital >= 10:

        btc = 10 / price
        capital -= 10
        position_price = price

        last_trade_time = now

        print("BUY:", price)

    # SELL
    elif btc > 0:

        if price > position_price + 20:

            capital += btc * price
            btc = 0

            last_trade_time = now

            print("SELL:", price)

    total = capital + btc * price

    print("Capital:", round(total,2))
