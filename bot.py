import ccxt
import time

print("Simulador de Grid iniciado")

exchange = ccxt.mexc()

symbol = "BTC/USDT"

capital_usdt = 50
btc_balance = 0

grid_lower = 64000
grid_upper = 66000
grid_levels = 10

step = (grid_upper - grid_lower) / grid_levels

grid = [grid_lower + step*i for i in range(grid_levels+1)]

print("GRID:", grid)

while True:

    ticker = exchange.fetch_ticker(symbol)
    price = ticker["last"]

    print("Preço atual:", price)

    for level in grid:

        if price <= level and capital_usdt > 5:

            btc_buy = 5 / price

            btc_balance += btc_buy
            capital_usdt -= 5

            print("SIMULADO BUY:", price)

        if price >= level and btc_balance > 0:

            usdt_sell = btc_balance * price

            capital_usdt += usdt_sell
            btc_balance = 0

            print("SIMULADO SELL:", price)

    total = capital_usdt + btc_balance * price

    print("Capital:", total)

    time.sleep(20)
