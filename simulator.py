capital_usdt = 50
btc_balance = 0

def simulate(price, grid):

    global capital_usdt
    global btc_balance

    for level in grid:

        if price <= level and capital_usdt >= 5:

            btc_buy = 5 / price
            btc_balance += btc_buy
            capital_usdt -= 5

            print("BUY SIMULADO:", price)

        elif price >= level and btc_balance > 0:

            usdt_sell = btc_balance * price
            capital_usdt += usdt_sell
            btc_balance = 0

            print("SELL SIMULADO:", price)

    total = capital_usdt + btc_balance * price

    print("Capital atual:", round(total,2))
