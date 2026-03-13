import time

from exchange import get_price
from strategy import create_grid
from simulator import simulate

print("BOT SIMULADOR INICIADO")

grid = None

while True:

    try:

        price = get_price()

        print("Preço BTC:", price)

        if grid is None:
            grid = create_grid(price)
            print("GRID:", grid)

        simulate(price, grid)

    except Exception as e:

        print("Erro:", e)

    time.sleep(15)
