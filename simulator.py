capital = 50
btc = 0

position_price = None

def trade(price):

    global capital
    global btc
    global position_price

    # BUY
    if btc == 0 and capital >= 10:

        btc = 10 / price
        capital -= 10
        position_price = price

        print("BUY:", price)

    # SELL
    elif btc > 0:

        if price > position_price + 20:

            capital += btc * price
            btc = 0

            print("SELL:", price)

    total = capital + btc * price

    print("Capital:", round(total,2))
