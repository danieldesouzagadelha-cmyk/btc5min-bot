import time
import traceback

from simulador import trade
from mercado import get_market_data

print("===================================")
print("     LIQUIDITY REVERSION BOT       ")
print("===================================")

loop = 0

while True:

    try:

        loop += 1
        print("\nLoop:", loop)

        # =========================
        # PEGAR DADOS DO MERCADO
        # =========================

        price, bid, ask, bid_volume, ask_volume = get_market_data()

        print("Preço:", price)
        print("Bid:", bid)
        print("Ask:", ask)

        # =========================
        # EXECUTAR ESTRATÉGIA
        # =========================

        trade(price, bid, ask, bid_volume, ask_volume)

        # =========================
        # ESPERA ENTRE LOOPS
        # =========================

        time.sleep(1)

    except Exception as e:

        print("ERRO:", e)
        traceback.print_exc()

        time.sleep(5)
