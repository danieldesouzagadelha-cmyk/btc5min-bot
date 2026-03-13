capital_usdt = 50
btc_balance = 0

active_buys = set()

def simulate(price, grid):

    global capital_usdt
    global btc_balance
    global active_buys

    for level in grid:

        # BUY
        if price <= level and level not in active_buys and capital_usdt >= 5:

            btc_buy = 5 / price
            btc_balance += btc_buy
            capital_usdt -= 5

            active_buys.add(level)

            print("BUY SIMULADO:", round(price,2))

        # SELL
        if price >= level and level in active_buys:

            btc_sell = btc_balance
            usdt_sell = btc_sell * price

            capital_usdt += usdt_sell
            btc_balance = 0

            active_buys.remove(level)

            print("SELL SIMULADO:", round(price,2))

    total = capital_usdt + btc_balance * price

    print("Capital atual:", round(total,2))
